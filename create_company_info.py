# create_company_info.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blitzhub.settings')
django.setup()

from website.models import CompanyInfo

CompanyInfo.objects.create(
    name="BlitzTech Electronics",
    address="904 Premium Close, Mount Pleasant, Business Park, Harare, Zimbabwe",
    phone="+263 774 613 020",
    email="sales@blitztechelectronics.co.zw",
    website="www.blitztechelectronics.co.zw",
    mission="To become the leading innovative electronic systems developers in Zimbabwe by exceeding customers' quality expectations through delivery of transcendent, tailor-made services of unstinting high quality and value addition.",
    vision="Elevation of our clients' business and lives through the power of custom-fit solutions",
    about_us="Our passion is, put simply, electronics, and its capacity to enable individuals to change the world. Just like every circuit and system we build starts with careful attention to details and individual components, the world we seek to change is built upon our focus on individual clients, and we value each client greatly."
)
