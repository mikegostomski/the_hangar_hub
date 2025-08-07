from base.models.utility.error import EnvHelper, Log, Error
from base_stripe.services import config_service
import stripe

log = Log()
env = EnvHelper()


class Account:
    """
    Represents a Connected Account in Stripe
    """
    id = None
    object = None
    business_profile = None
    business_type = None
    capabilities = None
    charges_enabled = None
    company = None
    controller = None
    country = None
    created = None
    default_currency = None
    details_submitted = None
    email = None
    external_accounts = None
    future_requirements = None
    login_links = None
    metadata = None
    payouts_enabled = None
    requirements = None
    settings = None
    tos_acceptance = None
    type = None

    @property
    def name(self):
        if self.business_profile:
            return self.business_profile.name
        elif self.company:
            return self.company.get("name")
        else:
            # ToDo: Individual name?
            return f"Account: {self.id}"

    def update_stripe(self):
        """
        Update values that may be updated via the API.
        Call after updating the values in this class.
        """
        try:
            config_service.set_stripe_api_key()
            # Since the accounts control themselves, most of this cannot be updated
            stripe.Account.modify(
                self.id,
                # business_profile=self.business_profile.to_dict(),
                # business_type=self.business_type,
                # capabilities={},
                # default_currency=self.default_currency,
                # email=self.email,
                metadata=self.metadata,
                # settings=self.settings.to_dict(),
                # tos_acceptance=self.tos_acceptance
            )
            log.info("Stripe account metadata has been updated")
        except Exception as ee:
            Error.unexpected("Unable to update account record in Stripe", ee)

    
    def __init__(self, api_response):
        if api_response:
            log.debug(api_response)
            self.id = api_response.get("id")
            self.object = api_response.get("object")
            self.business_type = api_response.get("business_type")
            self.capabilities = api_response.get("capabilities")
            self.charges_enabled = api_response.get("charges_enabled")
            self.country = api_response.get("country")
            self.company = api_response.get("company")
            self.created = api_response.get("created")
            self.default_currency = api_response.get("default_currency")
            self.details_submitted = api_response.get("details_submitted")
            self.email = api_response.get("email")
            self.external_accounts = api_response.get("external_accounts")
            self.future_requirements = api_response.get("future_requirements")
            self.login_links = api_response.get("login_links")
            self.metadata = api_response.get("metadata")
            self.payouts_enabled = api_response.get("payouts_enabled")
            self.requirements = api_response.get("requirements")
            self.tos_acceptance = api_response.get("tos_acceptance")
            self.type = api_response.get("type")
            
            # Create classes for these more complex attributes
            self.business_profile = _BusinessProfile(api_response.get("business_profile"))
            self.controller = api_response.get("controller")
            self.settings = api_response.get("settings")
            

class _BusinessProfile:
    annual_revenue = None
    estimated_worker_count = None
    mcc = None
    name = None
    product_description = None
    support_address = None
    support_email = None
    support_phone = None
    support_url = None
    url = None

    def to_dict(self):
        """Return contents for the update API"""
        return {
            # "annual_revenue": self.annual_revenue,
            "estimated_worker_count": self.estimated_worker_count,
            "mcc": self.mcc,
            "name": self.name,
            "product_description": self.product_description,
            "support_address": self.support_address,
            "support_email": self.support_email,
            "support_phone": self.support_phone,
            "support_url": self.support_url,
            "url": self.url,
        }
    
    def __init__(self, api_response):
        if api_response:
            self.annual_revenue = api_response.get("annual_revenue")
            self.estimated_worker_count = api_response.get("estimated_worker_count")
            self.mcc = api_response.get("mcc")
            self.name = api_response.get("name")
            self.product_description = api_response.get("product_description")
            self.support_address = api_response.get("support_address")
            self.support_email = api_response.get("support_email")
            self.support_phone = api_response.get("support_phone")
            self.support_url = api_response.get("support_url")
            self.url = api_response.get("url")
        

class _Controller:
    fees = None
    is_controller = None
    losses = None
    requirement_collection = None
    stripe_dashboard = None
    type = None

    def __init__(self, api_response):
        if api_response:
            self.fees = api_response.get("fees")
            self.is_controller = api_response.get("is_controller")
            self.losses = api_response.get("losses")
            self.requirement_collection = api_response.get("requirement_collection")
            self.stripe_dashboard = api_response.get("stripe_dashboard")
            self.type = api_response.get("type")
    
    
class _Settings:
    bacs_debit_payments = None
    bacs_debit_payments_display_name = None
    bacs_debit_payments_service_user_number = None

    branding = None
    branding_icon= None
    branding_logo= None
    branding_primary_color= None
    branding_secondary_color = None
    
    card_issuing = None
    card_issuing_tos_acceptance = None
    card_issuing_tos_acceptance_date = None
    card_issuing_tos_acceptance_ip = None
    
    card_payments = None
    card_payments_decline_on = None
    card_payments_decline_on_avs_failure = None
    card_payments_decline_on_cvc_failure = None
    card_payments_statement_descriptor_prefix = None
    card_payments_statement_descriptor_prefix_kanji = None
    card_payments_statement_descriptor_prefix_kana = None
 
    dashboard = None
    dashboard_display_name = None
    dashboard_timezone = None
    
    invoices = None
    invoices_default_account_tax_ids = None

    payments = None
    payments_statement_descriptor = None
    payments_statement_descriptor_kana = None
    payments_statement_descriptor_kanji = None
    
    payouts = None
    payouts_debit_negative_balances = None
    payouts_schedule = None
    payouts_schedule_delay_days = None
    payouts_schedule_interval = None
    payouts_statement_descriptor = None

    sepa_debit_payments: None

    def to_dict(self):
        """Return contents for the update API"""
        return {
            "bacs_debit_payments": {"display_name": self.bacs_debit_payments_display_name},
            "branding": {
                "icon": self.branding_icon,
                "logo": self.branding_logo,
                "primary_color": self.branding_primary_color,
                "secondary_color": self.branding_secondary_color,
            },
            # "card_issuing": {"tos_acceptance": {
            #     "date": self.card_issuing_tos_acceptance_date,
            #     "ip": self.card_issuing_tos_acceptance_ip,
            #     "user_agent": None
            # }},
            "card_payments": {"decline_on": {
                "avs_failure": self.card_payments_decline_on_avs_failure,
                "cvc_failure": self.card_payments_decline_on_cvc_failure
            }},
            "invoices": {
                "default_account_tax_ids": self.invoices_default_account_tax_ids,
                # "hosted_payment_method_save": None  # {"always", "never", "offer"}
            },
            "payments": {
                "statement_descriptor": self.payments_statement_descriptor,
                "statement_descriptor_prefix_kana": self.payments_statement_descriptor_kana,
                "statement_descriptor_prefix_kanji": self.payments_statement_descriptor_kanji,
            },
            "payouts": {
                "debit_negative_balances": self.payouts_debit_negative_balances,
                "schedule": {
                    "delay_days": self.payouts_schedule_delay_days,
                    "interval": self.payouts_schedule_interval,
                },
                "statement_descriptor": self.payouts_statement_descriptor,
            },
        }


    def __init__(self, api_response):
        if api_response:
            self.bacs_debit_payments = api_response.get("bacs_debit_payments")
            self.bacs_debit_payments_display_name = self.bacs_debit_payments.get("display_name")
            self.bacs_debit_payments_service_user_number = self.bacs_debit_payments.get("service_user_number")
        
            self.branding = api_response.get("branding")
            self.branding_icon = self.branding.get("icon")
            self.branding_logo = self.branding.get("logo")
            self.branding_primary_color = self.branding.get("primary_color")
            self.branding_secondary_color = self.branding.get("secondary_color")
            
            self.card_issuing = api_response.get("card_issuing")
            self.card_issuing_tos_acceptance = self.card_issuing.get("tos_acceptance")
            self.card_issuing_tos_acceptance_date = self.card_issuing_tos_acceptance.get("date")
            self.card_issuing_tos_acceptance_ip = self.card_issuing_tos_acceptance.get("ip")
            
            self.card_payments = api_response.get("card_payments")
            self.card_payments_decline_on = self.card_payments.get("decline_on")
            self.card_payments_decline_on_avs_failure = self.card_payments_decline_on.get("avs_failure")
            self.card_payments_decline_on_cvc_failure = self.card_payments_decline_on.get("cvc_failure")
            self.card_payments_statement_descriptor_prefix = self.card_payments.get("statement_descriptor_prefix")
            self.card_payments_statement_descriptor_prefix_kanji = self.card_payments.get("statement_descriptor_prefix_kanji")
            self.card_payments_statement_descriptor_prefix_kana = self.card_payments.get("statement_descriptor_prefix_kana")
         
            self.dashboard = api_response.get("dashboard")
            self.dashboard_display_name = self.dashboard.get("display_name")
            self.dashboard_timezone = self.dashboard.get("timezone")
            
            self.invoices = api_response.get("invoices")
            self.invoices_default_account_tax_ids = self.invoices.get("default_account_tax_ids")
        
            self.payments = api_response.get("payments")
            self.payments_statement_descriptor = self.payments.get("statement_descriptor")
            self.payments_statement_descriptor_kana = self.payments.get("statement_descriptor_kana")
            self.payments_statement_descriptor_kanji = self.payments.get("statement_descriptor_kanji")
            
            self.payouts = api_response.get("payouts")
            self.payouts_debit_negative_balances = self.payouts.get("debit_negative_balances")
            self.payouts_schedule = self.payouts.get("schedule")
            self.payouts_schedule_delay_days = self.payouts_schedule.get("delay_days")
            self.payouts_schedule_interval = self.payouts_schedule.get("interval")
            self.payouts_statement_descriptor = self.payouts.get("statement_descriptor")
        
            self.sepa_debit_payments = api_response.get("sepa_debit_payments")
            