from django.contrib.messages import success

from base.models.utility.error import EnvHelper, Log, Error
import stripe
from base.services import message_service
from base.services.message_service import post_success
from base_stripe.services.config_service import set_stripe_api_key
from datetime import datetime, timezone, timedelta
from the_hangar_hub.services.rental import invoice_svc


log = Log()
env = EnvHelper()

def terminate_rental_agreement(rental_agreement):
    """
    Terminate a rental agreement, including the following steps:
        1. Set end date (now)
        2. Cancel Stripe subscription(s)
        3. Cancel open invoices
        4. Confirmation email to the tenant

    Returns: True/False to indicate termination success
    """
    log.trace([rental_agreement])

    if not rental_agreement:
        return False

    # Set rental agreement end date
    try:
        now = datetime.now(timezone.utc)
        if rental_agreement.end_date and rental_agreement.end_date < now:
            message_service.post_warning("Rental agreement was previously terminated.")
            # Continue in case there are subscriptions or invoices to cancel
        else:
            rental_agreement.end_date = now
            rental_agreement.save()
    except Exception as ee:
        Error.unexpected(
            "Unable to set rental agreement end date. Agreement was not cancelled.",
            ee, rental_agreement
        )
        return False

    # Continue with remaining steps even if some of them, fail
    issues = False
    status = False

    # Terminate subscriptions
    if rental_agreement.active_subscription:
        canceled_subscriptions = uncanceled_subscriptions = 0
        try:
            if rental_agreement.stripe_subscription:
                set_stripe_api_key()
                stripe.Subscription.cancel(
                    rental_agreement.stripe_subscription.stripe_id,
                    stripe_account=rental_agreement.airport.stripe_account.stripe_id
                )
                canceled_subscriptions += 1
                # Celery will react to this
        except Exception as ee:
            Error.record(ee, rental_agreement.stripe_subscription)
            uncanceled_subscriptions += 1

        try:
            # May also have had an active future subscription
            if rental_agreement.future_stripe_subscription:
                set_stripe_api_key()
                stripe.Subscription.cancel(
                    rental_agreement.future_stripe_subscription.stripe_id,
                    stripe_account=rental_agreement.airport.stripe_account.stripe_id
                )
                canceled_subscriptions += 1
                # Celery will react to this
        except Exception as ee:
            Error.record(ee, rental_agreement.future_stripe_subscription)
            uncanceled_subscriptions += 1

        if canceled_subscriptions:
            s = "" if canceled_subscriptions == 1 else "s"
            message_service.post_success(f"Cancelled {canceled_subscriptions} active subscription{s}")
        if uncanceled_subscriptions:
            issues = True
            s = "" if uncanceled_subscriptions == 1 else "s"
            message_service.post_error(f"Unable to cancel {uncanceled_subscriptions} active subscription{s}")

        # If at least one active subscription was canceled, consider a success
        status = canceled_subscriptions > 0
    else:
        message_service.post_info("No active subscriptions to cancel.")
        # Just setting the date should be enough to consider a success in this case
        status = True


    # Cancel any open invoices
    canceled_invoices = uncanceled_invoices = 0
    if rental_agreement.open_invoice_models():
        for invoice in rental_agreement.open_invoice_models():
            try:
                if invoice_svc.cancel_invoice(invoice):
                    canceled_invoices += 1
                else:
                    uncanceled_invoices += 1
            except Exception as ee:
                Error.record(ee, invoice)
                uncanceled_invoices += 1
        if canceled_invoices:
            s = "" if canceled_invoices == 1 else "s"
            message_service.post_success(f"Cancelled {canceled_invoices} open invoice{s}")
        if uncanceled_invoices:
            issues = True
            s = "" if uncanceled_invoices == 1 else "s"
            message_service.post_error(f"Unable to cancel {uncanceled_invoices} open invoice{s}")
    else:
        message_service.post_info("No open invoices to cancel.")

    if status and issues:
        message_service.post_info("Rental agreement was terminated with some issues.")
    elif status:
        message_service,post_success("Rental agreement was terminated.")
    else:
        message_service.post_error("Unable to terminate rental agreement")

    # ToDo: Send email confirmation to tenant. (might be done via celery if Stripe subscription existed)

    return not issues






