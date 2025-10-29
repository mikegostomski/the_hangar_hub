from django.http import HttpResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from base.models.utility.error import Error
from base.classes.util.env_helper import Log, EnvHelper
from base_stripe.services import product_service
from django.views.decorators.csrf import csrf_exempt
import stripe
from base_stripe.models.events import StripeWebhookEvent
from base_stripe.services import webhook_service, config_service
from the_hangar_hub.tasks import process_stripe_event


log = Log()
env = EnvHelper()

# ToDo: Error Handling/Messages


@csrf_exempt
def webhook(request):
    try:
        result = StripeWebhookEvent.receive(request)
        status_code = result if str(result).isnumeric() else 200
        if status_code == 200:
            process_stripe_event.delay(result.id)
        return HttpResponse(status=status_code)
    except Exception as ee:
        Error.record(ee)


def react_to_events(request):
    """
    Webhook events get recorded to the Django database.
    This endpoint refreshes any models tied to the objects in those events
    (customers, subscriptions, and invoices)
    """
    return JsonResponse(webhook_service.react_to_events())

def reset_sandbox(request):
    """
    Delete test customers and subscriptions from sandbox
    """
    if env.is_prod:
        log.error("Cannot delete test data in production")
        return HttpResponseForbidden()

    config_service.set_stripe_api_key()

    # 1. Cancel all active subscriptions
    for sub in stripe.Subscription.list(status='active', limit=100).auto_paging_iter():
        stripe.Subscription.delete(sub.id)

    # 2. Delete all customers
    for cust in stripe.Customer.list(limit=100).auto_paging_iter():
        stripe.Customer.delete(cust.id)

    return HttpResponse("Completed")



def show_prices(request):
    prices = product_service.get_price_list()
    return render(
        request, "base/stripe/prices/index.html",
        {
            "prices": prices,
        }
    )

def show_accounts(request):
    return HttpResponseForbidden()


def modify_account(request):
    return HttpResponseForbidden()


