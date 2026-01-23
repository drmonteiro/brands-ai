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
    except:
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
    """Generate HTML email content for partnership proposal"""
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Georgia', serif; color: #1e293b; line-height: 1.6; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
    .header {{ border-bottom: 2px solid #1e293b; padding-bottom: 20px; margin-bottom: 30px; }}
    .logo {{ font-size: 24px; font-weight: bold; color: #1e293b; }}
    .content {{ margin-bottom: 30px; }}
    .signature {{ margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
    .footer {{ text-align: center; color: #64748b; font-size: 12px; margin-top: 40px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo">Confeções Lança</div>
      <div style="color: #64748b; font-size: 14px;">Since 1973 • Premium Portuguese Manufacturing</div>
    </div>
    
    <div class="content">
      <p>Dear {brand.name} Team,</p>
      
      <p>
        We are reaching out from <strong>Confeções Lança</strong>, a Portuguese garment manufacturer 
        with over 50 years of excellence in producing superior quality menswear. We specialize in 
        tailored suits, overcoats, vests, and trench coats using avant-garde production technologies 
        and premium fabrics.
      </p>
      
      <p>
        We have identified {brand.name} as an exceptional brand that shares our commitment to quality 
        and craftsmanship. Your positioning in the premium menswear market (average suit price: 
        ${brand.average_suit_price_usd:.0f}) aligns perfectly with our manufacturing capabilities.
      </p>
      
      <p><strong>Why Partner with Confeções Lança?</strong></p>
      <ul>
        <li>🎯 <strong>Specialized Manufacturing:</strong> Tailored suits and premium outerwear</li>
        <li>⚙️ <strong>Advanced Technology:</strong> Laser cutting and precision manufacturing</li>
        <li>🌍 <strong>Sustainability Focus:</strong> Renewable energy and waste management</li>
        <li>✨ <strong>Flexibility:</strong> Both industrial scale and tailor-made models</li>
        <li>📜 <strong>Quality Certification:</strong> Structured processes ensuring excellence</li>
      </ul>
      
      <p>
        We would be delighted to discuss how we can support {brand.name}'s growth with 
        our manufacturing expertise. Our team is ready to provide samples and detailed information 
        about our capabilities.
      </p>
      
      <p>
        Would you be available for a brief call next week to explore this partnership opportunity?
      </p>
    </div>
    
    <div class="signature">
      <p>Best regards,</p>
      <p>
        <strong>Commercial Team</strong><br>
        Confeções Lança<br>
        Covilhã, Portugal<br>
        Email: comercial@confecos-lanca.pt
      </p>
    </div>
    
    <div class="footer">
      <p>Confeções Lança • Established 1973 • Excellence in Portuguese Manufacturing</p>
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
            "to": [contact_email],
            "subject": f"Partnership Opportunity from Confeções Lança - Premium Portuguese Manufacturing",
            "html": generate_email_html(brand),
            "text": generate_email_text(brand),
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
