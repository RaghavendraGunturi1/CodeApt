from django.conf import settings
from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
from phonepe.sdk.pg.env import Env

def get_phonepe_client():
    """
    Singleton initialization of PhonePe StandardCheckoutClient (v2).
    """
    # 1. Determine Environment
    # The docs say: Env.SANDBOX or Env.PRODUCTION
    env = Env.SANDBOX if settings.PHONEPE_ENV == 'SANDBOX' else Env.PRODUCTION

    # 2. Initialize Client
    # The SDK manages the instance internally
    client = StandardCheckoutClient.get_instance(
        client_id=settings.PHONEPE_CLIENT_ID,
        client_secret=settings.PHONEPE_CLIENT_SECRET,
        client_version=settings.PHONEPE_CLIENT_VERSION,
        env=env,
        should_publish_events=False # As per your sample code
    )
    
    return client