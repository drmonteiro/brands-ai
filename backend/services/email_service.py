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
    llm = get_llm(fast=False, temperature=1.0)
    
    # Build context for personalization
    recipient = brand.contact_name or "Director / Founder"
    brand_price = f"${brand.average_suit_price_usd:.0f}" if brand.average_suit_price_usd else "Premium"
    style = brand.brand_style or "Premium Menswear"
    city = brand.city or "your city"
    
    prompt = f"""
    Write a highly professional B2B partnership proposal email from Confeções Lança (Portuguese quality menswear manufacturer) to {brand.name}.
    
    CONTEXT ABOUT THE TARGET BRAND:
    - Name: {brand.name}
    - Location: {city}
    - Segment: {style}
    - Price Point: {brand_price} (Retail price for suits)
    - Decision Maker: {recipient}
    
    ABOUT CONFEÇÕES LANÇA:
    - Specialization: Quality tailored suits, trousers, waistcoats, overcoats, and formalwear.
    - Legacy: Since 1973 (50+ years of expertise).
    - Origin: Covilhã, Portugal (Historical textile hub).
    - Clients: Manufacturing for well-known mid-to-high range menswear brands and independent boutiques across Europe.
    - Advantage: Mix of high-tech production (laser cutting) with hand-finishing flexibility (sartorial models).
    - Own Label: Capable of producing own label collections for retail partners.
    
    THE EMAIL SHOULD:
    1. Be concise (max 180 words).
    2. Start by acknowledging {brand.name}'s specific positioning in {city}.
    3. Suggest that their price point of {brand_price} is a perfect fit for Lança's quality manufacturing.
    4. Propose a short 15-minute introductory call.
    5. Avoid sounding desperate; focus on European craftsmanship and reliable partnership.
    6. Mention that {brand.name} was selected specifically by our AI-driven market analysis as a "top fit" brand.
    
    Return ONLY the email body in English. No subject line.
    """
    
    try:
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"[EMAIL-AI] Could not generate personalized draft: {e}")
        return generate_email_text(brand)

def generate_email_text(brand: BrandLead) -> str:
    """Generate plain text version of email"""
    return f"""
Dear {brand.name} Team,

We are reaching out from Confeções Lança, a Portuguese garment manufacturer with over 50 years of excellence in producing superior quality menswear. We specialize in tailored suits, overcoats, vests, and trench coats using avant-garde production technologies and premium fabrics.

We have identified {brand.name} as an exceptional brand that shares our commitment to quality and craftsmanship. Your positioning in the premium menswear market (average suit price: ${brand.average_suit_price_usd:.0f}) aligns perfectly with our manufacturing capabilities.

Why Partner with Confeções Lança?

• Specialized Manufacturing: Tailored suits and premium outerwear
• Advanced Technology: Laser cutting and precision manufacturing
• Sustainability Focus: Renewable energy and waste management
• Flexibility: Both industrial scale and tailor-made models
• Quality Certification: Structured processes ensuring excellence

We would be delighted to discuss how we can support {brand.name}'s growth with our manufacturing expertise. Our team is ready to provide samples and detailed information about our capabilities.

Would you be available for a brief call next week to explore this partnership opportunity?

Best regards,

Commercial Team
Confeções Lança
Covilhã, Portugal
Email: comercial@confecos-lanca.pt

---
Confeções Lança • Established 1973 • Excellence in Portuguese Manufacturing
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
