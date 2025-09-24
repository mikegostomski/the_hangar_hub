from base.models.utility.error import EnvHelper, Log, Error
from base_stripe.models.events import WebhookEvent
import json
import stripe

log = Log()
env = EnvHelper()

ignorable_events = [
    "invoiceitem.created",
    "transfer.created",
    "application_fee.created",
]


class WebhookValidation:
    valid_request = False
    ignore = False
    status_code = 500

    event = None
    event_type = None
    event_id = None

    webhook_event_id = None

    @property
    def object_data(self):
        return self.event['data']['object']

    @property
    def object_type(self):
        return self.object_data.get('object')

    @property
    def object_id(self):
        return self.object_data.get('id')

    def __init__(self):
        pass

    @classmethod
    def validate(cls, request):
        response = WebhookValidation()


        # Return 200 OK for GET requests (for health checks)
        if request.method != 'POST':
            response.ignore = True
            response.status_code = 200
            response.valid_request = True
            return response

        # Validate Stripe signature
        webhook_secret = env.get_setting("STRIPE_WEBHOOK_SECRET")
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        if not sig_header:
            log.error("No Stripe signature header found - possible unauthorized request")
            response.status_code = 400
            return response

        # Process the payload from Stripe
        try:
            payload = request.body
            payload_text = payload.decode('utf-8')
            payload_json = json.loads(payload_text)
        except Exception as ee:
            Error.record(ee)
            response.status_code = 500
            return response

        # Get the event and verify it
        try:
            response.event_type = payload_json.get('type', 'unknown')
            response.event_id = payload_json.get('id', 'unknown')
            log.info(f"Event: <{response.event_type}: {response.event_id}>")

            # Verify the event is from Stripe
            response.event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            log.info(f"Successfully validated Stripe webhook event")

            if not response.object_id:
                log.info(f"No object ID in webhook response:\n{payload_text}")
                return response

            log.info(f"Webhook Object: <{response.object_type}: {response.object_id}>")

            response.valid_request = True
            response.status_code = 200

            try:
                # Per API docs, the object data should be re-queried, because it may be out-of-date by the time
                # the webhook is received. Also, processing should be done asynchronously to prevent Stripe from
                # re-sending the request after a time-out.
                # Therefore, just save the object ID in the database to be processed by the app later.

                if response.event_type not in ignorable_events:
                    whe = WebhookEvent.objects.create(
                        event_type=response.event_type,
                        event_id=response.event_id,
                        object_type=response.object_type,
                        object_id=response.object_id,
                    )
                    log.info(f"Webhook Event Logged: {whe}")
                    response.webhook_event_id = whe.id
            except Exception as ee:
                Error.record(ee, "Creating WebhookEvent record")

            return response

        except json.JSONDecodeError:
            Error.record("Could not parse JSON payload")
            response.status_code = 500
            return response
        except stripe.error.SignatureVerificationError as ee:
            Error.record(ee, "Invalid Stripe signature")
            response.status_code = 400
            return response
        except Exception as ee:
            Error.record(ee)
            response.status_code = 500
            return response
