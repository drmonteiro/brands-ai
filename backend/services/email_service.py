"""
Email Service for Confeções Lança
Handles sending partnership proposal emails using Resend API
"""

from urllib.parse import urlparse
import resend

from config import Config
from models import BrandLead


def init_resend():
    """Initialize Resend with API key"""
    resend.api_key = Config.RESEND_API_KEY


def get_contact_email(brand: BrandLead) -> str:
    """Generate contact email address for a brand"""
    try:
        parsed = urlparse(brand.website_url)
        domain = parsed.hostname or ""
        domain = domain.replace("www.", "")
        return f"info@{domain}"
    except Exception:
        return "info@example.com"


async def generate_personalized_outreach(brand: BrandLead) -> str:
    """
    Generate a highly personalized outreach email using LLM.
    Refers to the brand's specific price point and positioning.
    """
    from agents.nodes.utils import get_llm
    
    # We use the deep model for outreach generation to ensure high quality
    llm = get_llm(fast=False, temperature=0.7)
    
    # Build context for personalization
    recipient = brand.contact_name or "Director / Founder"
    brand_price = f"${brand.average_suit_price_usd:.0f}" if brand.average_suit_price_usd else "Premium"
    style = brand.brand_style or "Premium Menswear"
    city = brand.city or "your city"
    
    prompt = f"""
    Write a highly professional B2B partnership proposal email from Confeções Lança (Portuguese quality menswear manufacturer) to {brand.name}.
    
    You MUST use the following structure and content as requested by the client, but you can add small personalizations to make it feel more authentic for {brand.name} in {city}.
    
    BASE TEMPLATE:
    Dear [Name/Team],
    Having reviewed your brand online, we were very impressed with your retail presence and product offer.
    I’m writing to introduce a tailoring manufacturer based in central Portugal. Established in 1973, the company has extensive experience supplying own-label garments to global brands, retail groups, and independent businesses.
    We bring a strong depth of expertise, combining flexibility with consistent quality and service, along with pricing that supports healthy margins. With many clients based in the UK, we’ve developed a refined level of make, as well as the ability to respond to more demanding product development briefs.
    We offer two levels of jacket construction: canvas fused and traditional half canvas with a padded lapel. Production can be developed from in-house blocks or created entirely to your direction. In addition, we manufacture completely unstructured jackets, as well as formal and casual trousers, waistcoats, and coats, primarily in wool blends. Should you have any other specific styles in mind, we would be very happy to review and develop these with you.
    We believe this could represent a strong partnership in producing high-quality garments and would welcome the opportunity to explore this further. I’d be happy to arrange a short 15-minute call to introduce things in more detail and discuss potential collaboration.
    Thank you for your time, and I look forward to hearing from you.
    Warm regards
    
    INFO TO USE FOR PERSONALIZATION:
    - Target Brand: {brand.name}
    - Location: {city}
    - Segment: {style}
    - Decision Maker: {recipient}
    
    Return ONLY the email body in English. No subject line.
    """
    
    try:
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"[EMAIL-AI] Could not generate personalized draft: {e}")
        return generate_email_text(brand)

def generate_email_text(brand: BrandLead) -> str:
    """Generate plain text version of email using the client's preferred template"""
    recipient = brand.contact_name or "Team"
    return f"""
Dear {recipient},

Having reviewed your brand online, we were very impressed with your retail presence and product offer.

I’m writing to introduce a tailoring manufacturer based in central Portugal. Established in 1973, the company has extensive experience supplying own-label garments to global brands, retail groups, and independent businesses.

We bring a strong depth of expertise, combining flexibility with consistent quality and service, along with pricing that supports healthy margins. With many clients based in the UK, we’ve developed a refined level of make, as well as the ability to respond to more demanding product development briefs.

We offer two levels of jacket construction: canvas fused and traditional half canvas with a padded lapel. Production can be developed from in-house blocks or created entirely to your direction. In addition, we manufacture completely unstructured jackets, as well as formal and casual trousers, waistcoats, and coats, primarily in wool blends. Should you have any other specific styles in mind, we would be very happy to review and develop these with you.

We believe this could represent a strong partnership in producing high-quality garments and would welcome the opportunity to explore this further. I’d be happy to arrange a short 15-minute call to introduce things in more detail and discuss potential collaboration.

Thank you for your time, and I look forward to hearing from you.

Warm regards,

Commercial Team
Confeções Lança
    """.strip()


def generate_email_html(brand: BrandLead, ai_draft: str = "") -> str:
    """Generate HTML email content for INTERNAL ALERT"""
    draft_html = ""
    if ai_draft:
        draft_html = f"""
        <div style="background-color: #fffbeb; padding: 20px; border: 1px border #fcd34d; border-radius: 8px; margin: 20px 0;">
            <h3 style="margin-top:0; color: #92400e;">📝 Rascunho de Proposta (IA)</h3>
            <p style="font-style: italic; color: #b45309; font-size: 13px; margin-bottom: 15px;">Este rascunho foi personalizado com base no posicionamento da {brand.name}.</p>
            <div style="white-space: pre-wrap; font-family: 'Courier New', Courier, monospace; font-size: 14px; color: #451a03; background: white; padding: 15px; border-radius: 4px;">{ai_draft}</div>
        </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px; }}
    .header {{ background-color: #f8fafc; padding: 15px; border-bottom: 1px solid #e2e8f0; margin-bottom: 20px; border-radius: 8px 8px 0 0; }}
    .tag {{ display: inline-block; padding: 4px 8px; background-color: #e0f2fe; color: #0369a1; border-radius: 4px; font-size: 12px; font-weight: bold; }}
    .metric {{ margin-bottom: 10px; }}
    .label {{ font-weight: bold; color: #64748b; font-size: 14px; }}
    .value {{ font-size: 16px; color: #0f172a; }}
    .button {{ display: inline-block; background-color: #0f172a; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; margin-top: 20px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 style="margin:0; color: #0f172a;">🚀 Novo Potencial Cliente Detetado</h2>
    </div>
    
    <div class="content">
      <p>Olá Daniel e Carla,</p>
      <p>Existe uma excelente oportunidade de negócio com o cliente <strong>{brand.name}</strong>.</p>
      
      {draft_html}

      <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h3 style="margin-top:0;">{brand.name}</h3>
        <p><a href="{brand.website_url}" target="_blank">{brand.website_url}</a></p>
        
        <div class="metric">
          <span class="label">Cidade:</span><br>
          <span class="value">{brand.city}, {brand.origin_country}</span>
        </div>
        
        <div class="metric">
          <span class="label">Preço Médio Fato:</span><br>
          <span class="value">{f"€{brand.avg_suit_price_eur:.0f}" if brand.avg_suit_price_eur and brand.avg_suit_price_eur > 0 else f"${brand.average_suit_price_usd:.0f}"}</span>
        </div>
        
        <div class="metric">
          <span class="label">Estilo:</span><br>
          <span class="value">{brand.brand_style}</span>
        </div>

        <div class="metric">
          <span class="label">Descrição:</span><br>
          <span class="value">{brand.company_overview}</span>
        </div>
      </div>
      
      <p>Este cliente foi validado automaticamente com base nos critérios dos top 18 clientes Lança.</p>
      
      <a href="{brand.website_url}" class="button">Visitar Website</a>
    </div>
    
    <div style="margin-top: 30px; font-size: 12px; color: #94a3b8; text-align: center;">
      Enviado automaticamente pelo Lança Prospector AI
    </div>
  </div>
</body>
</html>
    """.strip()


async def send_partnership_email(brand: BrandLead) -> dict:
    """
    Send partnership proposal email to a brand using Resend API.
    
    Returns:
        dict with 'success' boolean and optional 'error' string
    """
    try:
        init_resend()
        
        print(f"[EMAIL] Generating AI draft and sending email to interior: {brand.name}")
        
        # [V3] Generate personalized AI draft
        ai_draft = await generate_personalized_outreach(brand)
        
        params = {
            "from": Config.FROM_EMAIL,
            "to": ["d.rmonteiro@hotmail.com", "carla.gaudencio@confeccoeslanca.com"],
            "reply_to": "d.rmonteiro@hotmail.com",
            "subject": f"🔥 Oportunidade: {brand.name} ({brand.city})",
            "html": generate_email_html(brand, ai_draft),
            "text": f"Nova oportunidade: {brand.name}\n\nPROPOSTA IA:\n{ai_draft}",
        }
        
        result = resend.Emails.send(params)
        
        print(f"[EMAIL] ✅ Email sent successfully: {result}")
        
        return {"success": True}
        
    except Exception as error:
        print(f"[EMAIL] ❌ Error sending email: {error}")
        return {
            "success": False,
            "error": str(error),
        }
