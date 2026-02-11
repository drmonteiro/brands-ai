
import asyncio
import os
import resend
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)

api_key = os.getenv("RESEND_API_KEY")

class MockBrand:
    def __init__(self):
        self.name = "Marca Exemplo"
        self.website_url = "https://example.com"
        self.store_count = 3
        self.average_suit_price_usd = 1200
        self.avg_suit_price_eur = 1100
        self.city = "Lisboa"
        self.origin_country = "Portugal"
        self.brand_style = "Bespoke"
        self.company_overview = "Esta marca é um excelente parceiro pois foca-se em fatos por medida de alta qualidade e procura expandir a sua linha de pronto-a-vestir." 

if not api_key:
    # Just mock for local test if key missing, but here we want to send
    pass

resend.api_key = api_key

# Import internal service to test the template generation logic
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.email_service import generate_email_html, send_partnership_email

async def test_send():
    brand = MockBrand()
    
    print("Testing email generation with Portuguese description...")
    html = generate_email_html(brand)
    
    if "Esta marca é um excelente parceiro" in html and "Olá Daniel e Carla" in html:
        print("✅ HTML Template verified: Contains Portuguese description and new greeting.")
    else:
        print("❌ HTML Template verification failed!")
        print("Greeting check:", "Olá Daniel e Carla" in html)
        print("Description check:", "Esta marca é um excelente parceiro" in html)

    # actually send to verify
    try:
        if api_key:
            print(f"Sending test email to verify appearance...")
            # We can't use send_partnership_email directly as it might not be async/await compatible in this script context easily without full setup 
            # but let's try calling the direct resend call like before to be safe
            params = {
                "from": "onboarding@resend.dev",
                "to": ["d.rmonteiro@hotmail.com"], 
                "reply_to": "d.rmonteiro@hotmail.com",
                "subject": "Teste de Email - Descrição em Português",
                "html": html,
                "text": "Teste",
            }
            resend.Emails.send(params)
            print("✅ Email sent successfully.")
    except Exception as e:
        print(f"Error sending: {e}")

if __name__ == "__main__":
    asyncio.run(test_send())
