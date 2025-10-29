from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
import json
import stripe

log = Log()
env = EnvHelper()


class StripeWebhookEvent(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    event_type = models.CharField(max_length=60)
    event_id = models.CharField(max_length=60)

    account_id = models.CharField(max_length=60, db_index=True, null=True, blank=True)
    object_type = models.CharField(max_length=60, db_index=True)
    object_id = models.CharField(max_length=60, db_index=True)

    refreshed = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)

    @classmethod
    def get(cls, xx):
        try:
            return cls.objects.get(pk=xx)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def receive(cls, request):
        try:
            # Return 200 OK for GET requests (for health checks)
            if request.method != 'POST':
                return 200

            webhook_secret = env.get_setting("STRIPE_WEBHOOK_SECRET")
            sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
            if not sig_header:
                log.error("No Stripe signature header found - possible unauthorized request")
                return 400

            payload = request.body
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            payload_data = json.loads(payload.decode('utf-8'))
            log.info(f"Successfully validated Stripe webhook event:\n{event}\n")
            """
            Sample event:
            {
              "account": "acct_1SJ0x54AGz0Ut3Ya", 
              "api_version": "2025-06-30.basil",
              "created": 1761751341,
              "data": {
                "object": {
                  "active": false,
                  "attributes": [],
                  "created": 1760463217,
                  "default_price": null,
                  "description": "Monthly rent payment",
                  "id": "prod_TEfRvyTmqjKlwG",
                  "images": [
                    "https://files.stripe.com/links/xxxxxx"
                  ],
                  "livemode": false,
                  "marketing_features": [],
                  "metadata": {},
                  "name": "Hangar Rent",
                  "object": "product",
                  "package_dimensions": null,
                  "shippable": null,
                  "statement_descriptor": null,
                  "tax_code": null,
                  "type": "service",
                  "unit_label": null,
                  "updated": 1761751341,
                  "url": null
                }
              },
              "id": "evt_1SNbCb4IRQMsYYrY3ZD3WxUq",
              "livemode": false,
              "object": "event",
              "pending_webhooks": 2,
              "request": {
                "id": "req_kxwQsus8y739Ae",
                "idempotency_key": null
              },
              "type": "product.deleted"
            }

            """
            log.info(f"Event payload:\n{payload_data}\n")
            """
            Sample payload_data:
            {
                'id': 'evt_1SNbCb4IRQMsYYrY3ZD3WxUq', 
                'object': 'event', 
                'account': 'acct_1SJ0x54AGz0Ut3Ya', 
                'api_version': '2025-06-30.basil', 
                'created': 1761751341, 
                'data': {
                    'object': {
                        'id': 'prod_TEfRvyTmqjKlwG', 
                        'object': 'product', 
                        'active': False, 
                        'attributes': [], 
                        'created': 1760463217, 
                        'default_price': None, 
                        'description': 'Monthly rent payment', 
                        'images': ['https://files.stripe.com/links/xxxxx'], 
                        'livemode': False, 
                        'marketing_features': [], 
                        'metadata': {}, 
                        'name': 'Hangar Rent', 
                        'package_dimensions': None, 
                        'shippable': None, 
                        'statement_descriptor': None,
                        'tax_code': None, 
                        'type': 'service', 
                        'unit_label': None, 
                        'updated': 1761751341, 
                        'url': None
                    }
                }, 
                'livemode': False, 
                'pending_webhooks': 2, 
                'request': {'id': 'req_kxwQsus8y739Ae', 'idempotency_key': None}, 
                'type': 'product.deleted'
            }
            """
        except Exception as ee:
            Error.record(ee)
            return 400

        event_id = payload_data.get('id', event.id)
        event_type = payload_data.get('type', event.type)
        object_data = payload_data.get('data').get('object')
        object_type = object_data.get("object")
        object_id = object_data.get("id")
        account_id = event.get('account')
        log.info(f"Event: <{event_type}: {event_id}> Account: {account_id}")

        if not object_id:
            if "balance" in event_type and "account" in payload_data:
                object_type = "account"
                object_id = account_id
            else:
                log.info(f"No object ID in webhook response:\n{payload_data}")
                return 500

        whe = cls.objects.create(
            event_type=event_type,
            event_id=event_id,
            object_type=object_type,
            object_id=object_id,
            account_id=event.get('account')
        )
        if whe:
            log.info(f"Webhook event created: {whe}")
        else:
            log.error("Unable to create WebhookEvent")

        return whe