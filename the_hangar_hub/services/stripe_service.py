from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.services import price_service, accounts_service, customer_service
from base_stripe.models.connected_account import ConnectedAccount
from datetime import datetime, timezone

log = Log()
env = EnvHelper()


def get_subscription_prices():
    return {price.lookup_key: price for  price in price_service.get_price_list() if price.name == "The Hangar Hub"}


def create_customer_from_airport(airport):
    log.trace([airport])

    if airport.stripe_customer_id:
        return True  # Already has customer ID, so consider a success

    try:
        set_stripe_api_key()
        customer = stripe.Customer.create(
            name=airport.display_name,
            email=airport.billing_email,
            phone=airport.billing_phone,
            address=get_stripe_address_dict(
                airport.billing_street_1,
                airport.billing_street_2,
                airport.billing_city,
                airport.billing_state,
                airport.billing_zip,
                airport.country
            ),
        )

        if customer and hasattr(customer, "id"):
            airport.stripe_customer_id = customer.id
            airport.save()
            log.info(f"{airport} is now Stripe customer: {airport.stripe_customer_id}")
            return True
        else:
            message_service.post_error("Unable to create customer record in payment portal.")
    except Exception as ee:
        Error.unexpected(
            "Unable to create customer record in payment portal", ee
        )
    return False


def get_customer_from_airport(airport):
    log.trace()

    if not airport.stripe_customer_id:
        return None

    try:
        set_stripe_api_key()
        customer = stripe.Customer.retrieve(airport.stripe_customer_id)

        if customer:
            return customer
        else:
            log.error("Unable to retrieve customer record from payment portal.")
    except Exception as ee:
        Error.record(ee, airport)
    return False

def modify_customer_from_airport(airport):
    log.trace()

    if not airport.stripe_customer_id:
        return None

    try:
        set_stripe_api_key()
        customer = stripe.Customer.modify(
            airport.stripe_customer_id,
            name=airport.display_name,
            email=airport.billing_email,
            phone=airport.billing_phone,
            address=get_stripe_address_dict(
                airport.billing_street_1,
                airport.billing_street_2,
                airport.billing_city,
                airport.billing_state,
                airport.billing_zip,
                airport.country
            ),
        )

        if customer:
            return customer
        else:
            log.error("Unable to retrieve customer record from payment portal.")
    except Exception as ee:
        Error.record(ee, airport)
    return False



def get_checkout_session_hh_subscription(airport, price_id):
    try:
        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            customer=airport.stripe_customer_id,
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{env.absolute_root_url}{reverse('airport:subscription_success', args=[airport.identifier])}",
            cancel_url=f"{env.absolute_root_url}{reverse('airport:subscription_failure', args=[airport.identifier])}",
        )
        co_session_id = checkout_session.id
        log.debug(f"CHECKOUT SESSION ID: {co_session_id}")
        return checkout_session
    except Exception as ee:
        Error.unexpected(
            "Unable to create a payment session", ee
        )
        return None


def create_connected_account(airport):
    log.trace([airport])

    if airport.stripe_account_id:
        # Already exists... return it
        return ConnectedAccount.get(airport.stripe_account_id)

    try:

        # Stripe uses two-digit country codes. Airport list was populated with three.
        if len(airport.country) == 3:
            # This works for USA and CAN. Future airports should import the 2-digit code
            airport.country = airport.country[:2]
            airport.save()

        params_dict = {
            "country": airport.country,
            "email": airport.billing_email,
            "capabilities": {
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            "controller": {
                "fees": {"payer": "account"},
                "stripe_dashboard": {"type": "full"},
            },
            "tos_acceptance": {"service_agreement": "full"},
            "business_type": "company",
            "business_profile": {
                "mcc": "4582",  # Code for airports
                "name": airport.display_name,
                "support_email": airport.billing_email,
                "support_phone": airport.billing_phone,
                "url": airport.url,
                "product_description": "Airport Payment",
            },
            "company": {
                "name": airport.display_name,
                "phone": airport.billing_phone,
                "address": get_stripe_address_dict(
                    airport.billing_street_1,
                    airport.billing_street_2,
                    airport.billing_city,
                    airport.billing_state,
                    airport.billing_zip,
                    airport.country,
                ),
            }
        }
        connected_account = accounts_service.create_account(params_dict)
        if connected_account:
            airport.stripe_account_id = connected_account.stripe_id
            airport.save()

    except Exception as ee:
        Error.record(ee, airport)
        return False


def get_onboarding_link(airport):
    link = accounts_service.create_account_onboarding_link(
        airport.stripe_account_id, reverse("manage:airport", args=[airport.identifier])
    )
    if link:
        return link.url
    else:
        return None

def get_account_login_link(airport):
    link = accounts_service.create_account_login_link(
        airport.stripe_account_id, reverse("manage:airport", args=[airport.identifier])
    )
    if link:
        return link.url
    else:
        return None

def sync_account_data(airport):
    stripe_data, local_data = accounts_service.get_connected_account(airport.stripe_account_id)


def create_rent_subscription(airport, rental, charge_automatically=False):
    if rental.has_subscription():
        return rental.stripe_subscription_id

    try:
        customer_email = rental.tenant.email
        customer_rec = customer_service.create_customer(
            rental.tenant.contact.display_name, customer_email, rental.tenant.user
        )
        if not customer_rec:
            message_service.post_error("Unable to create a subscription without a customer record")
            return None

        amount_due = int(rental.rent * 100)  # In cents

        billing_cycle_anchor = billing_cycle_anchor_config = None
        now = datetime.now(timezone.utc)
        if rental.start_date and rental.start_date > now:
            billing_cycle_anchor = int(rental.start_date.timestamp())
        elif rental.start_date:
            billing_cycle_anchor_config = {"day_of_month": rental.start_date.day}


        set_stripe_api_key()
        subscription = stripe.Subscription.create(
            customer=customer_rec.stripe_id,
            # currency="usd",  # ToDo: cad for airports in Canada
            description=f"Hanger {rental.hangar.code} at {airport.display_name}",
            items=[{
                "price_data": {
                    "unit_amount": amount_due,
                    "product": "prod_SlruA5rXT1JeD2",
                    "currency": "usd",  # ToDo: cad for airports in Canada
                    "recurring": {
                        "interval": "month",
                    }
                },
                "quantity": 1,
            }],
            application_fee_percent=1.0,  # ToDo: Make this a per-airport setting
            collection_method="charge_automatically" if charge_automatically else "send_invoice",
            days_until_due=7,
            invoice_settings={
                "issuer": {
                    "type": "account",
                    "account": airport.stripe_account_id
                }
            },
            on_behalf_of=airport.stripe_account_id,
            transfer_data={"destination": airport.stripe_account_id},
            billing_cycle_anchor=billing_cycle_anchor,
            billing_cycle_anchor_config=billing_cycle_anchor_config,
            proration_behavior="none",
        )

        subscription_id = subscription.get("id")
        try:
            rental.stripe_subscription_id = subscription_id
            rental.stripe_customer_id = customer_rec.stripe_id
            rental.save()
        except Exception as ee:
            Error.record(ee, subscription_id)

        return subscription_id
    except Exception as ee:
        Error.unexpected("Unable to create rental subscription", ee, rental)
        return None


def create_rent_invoice(airport, rental, charge_automatically=False):
    try:
        customer_email = rental.tenant.email
        customer_rec = customer_service.create_customer(
            rental.tenant.contact.display_name, customer_email, rental.tenant.user
        )
        if not customer_rec:
            message_service.post_error("Unable to create an invoice without a customer record")
            return None


        amount_due = int(rental.rent * 100)  # In cents

        # Calculate a due date
        # ToDo: Should manager specify due date manually?
        if charge_automatically:
            due_date = None
        elif rental.start_date:
            # If rental agreement started in the past, make invoice due today
            if rental.start_date < datetime.now(timezone.utc):
                due_date = int(datetime.now(timezone.utc).timestamp())
            # Otherwise, make it due on start date of rental agreement
            else:
                due_date = int(rental.start_date.timestamp())
        else:
            # When rental agreement date is not known, make due today
            due_date = int(datetime.now(timezone.utc).timestamp())
    except Exception as ee:
        Error.unexpected("Unable to process invoice parameters", ee, rental)
        return None

    # Create the invoice
    try:
        set_stripe_api_key()

        # invoice_item = stripe.InvoiceItem.create(
        #     customer=customer_rec.stripe_id,
        #     description=f"Hanger {rental.hangar.code}",
        #     price_data={
        #         "unit_amount": amount_due,
        #         "product": "prod_SlruA5rXT1JeD2",
        #         # "product_data": {"name": "Application Fee", "description": f"Hangar application at {airport.identifier}"},
        #         "currency": "usd",
        #     },
        #     quantity=1,
        # )

        log.info("Creating invoice...")
        invoice = stripe.Invoice.create(
            customer=customer_rec.stripe_id,
            description=f"Hanger {rental.hangar.code} at {airport.display_name}",
            # amount_due=amount_due,
            application_fee_amount=int(amount_due * 0.01),  # ToDo: Save fee amount per airport
            due_date=due_date,
            collection_method="charge_automatically" if charge_automatically else "send_invoice",
            issuer={
                "type": "account",
                "account": airport.stripe_account_id
            },
            on_behalf_of=airport.stripe_account_id,
            transfer_data={"destination": airport.stripe_account_id}
        )

        if invoice and invoice.get("object") == "invoice":
            invoice_id = invoice.get("id")

            log.info("Creating invoice line item...")
            inv_lines = stripe.Invoice.add_lines(
                invoice_id,
                lines=[
                    {"description": f"Hanger {rental.hangar.code}", "amount": amount_due},
                ]
            )
            if inv_lines and inv_lines.get("object") == "invoice":
                return inv_lines

            return invoice
        else:
            message_service.post_error(
                f"Unable to crete invoice for hanger {rental.hangar.code} ({rental.tenant.contact.display_name})"
            )
            return None
    except Exception as ee:
        Error.unexpected("Unable to create Stripe invoice", ee, rental)
        return None












def get_checkout_session_application_fee(application):
    try:
        airport = application.airport
        user_profile = Auth.lookup_user_profile(application.user, get_contact=True)
        customer_data = {"email": user_profile.email}
        phone = user_profile.phone_number()
        if phone:
            customer_data["phone"] = phone
        address = user_profile.contact().get_strip_address()
        if address:
            customer_data["address"] = {
                "line1": address.street_1,
                "line2": address.street_2,
                "city": address.city,
                "state": address.state,
                "postal_code": address.zip_code,
                "country": address.country,
            }
        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            # customer_data=customer_data,
            customer_email=user_profile.email,
            mode="payment",
            line_items=[
                {
                    'price_data': {
                        "unit_amount": airport.application_fee_stripe,
                        # "product": "prod_Slrtn5xjteLKes",
                        "product_data": {"name": "Application Fee", "description": f"Hangar application at {airport.identifier}"},
                        "currency": "usd",
                    },
                    'quantity': 1,
                },
            ],
            success_url=f"{env.absolute_root_url}{reverse('apply:record_payment', args=[application.id])}",
            cancel_url=f"{env.absolute_root_url}{reverse('apply:record_payment', args=[application.id])}",
            stripe_account= airport.stripe_account_id,
            # application_fee_amount=airport.application_fee_stripe * .01,  # 1% fee for HangarHub
        )
        co_session_id = checkout_session.id
        log.debug(f"CHECKOUT SESSION ID: {co_session_id}")
        return checkout_session
    except Exception as ee:
        Error.unexpected(
            "Unable to create a payment session", ee
        )
        return None


def get_session_details(session_id):
    try:
        set_stripe_api_key()
        return stripe.checkout.Session.retrieve(session_id)
    except Exception as ee:
        Error.unexpected(
            "Unable to retrieve checkout session status", ee
        )
        return None

def get_airport_subscriptions(airport):
    if airport and airport.stripe_customer_id:
        try:
            set_stripe_api_key()
            return stripe.Subscription.list(
                customer=airport.stripe_customer_id,
                expand=['data.latest_invoice.subscription_details']
            )
        except Exception as ee:
            Error.record(
                ee, f"get_airport_subscriptions({airport})"
            )
    return None


def get_customer_portal_session(airport):
    if airport and airport.stripe_customer_id:
        try:
            set_stripe_api_key()
            session = stripe.billing_portal.Session.create(
                customer=airport.stripe_customer_id,
                return_url=f"{env.absolute_root_url}{reverse('manage:airport', args=[airport.identifier])}",
            )
            if session and hasattr(session, "url"):
                return session.url
        except Exception as ee:
            Error.record(
                ee, f"get_customer_portal_session({airport})"
            )
    return None