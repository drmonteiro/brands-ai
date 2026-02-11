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


def generate_email_html(brand: BrandLead) -> str:
    """Generate HTML email content for INTERNAL ALERT"""
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
        
        print(f"[EMAIL] Sending partnership email to: {brand.name}")
        print(f"[EMAIL] Website: {brand.website_url}")
        print(f"[EMAIL] Store count: {brand.store_count}")
        print(f"[EMAIL] Avg price: ${brand.average_suit_price_usd:.0f}")
        
        contact_email = get_contact_email(brand)
        
        params = {
            "from": Config.FROM_EMAIL,
            "to": ["d.rmonteiro@hotmail.com", "carla.gaudencio@confeccoeslanca.com"],
            "reply_to": "d.rmonteiro@hotmail.com",
            "subject": f"Novo Potencial Cliente: {brand.name}",
            "html": generate_email_html(brand),
            "text": f"Novo cliente detetado: {brand.name}\nWebsite: {brand.website_url}\nCidade: {brand.city}",
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
