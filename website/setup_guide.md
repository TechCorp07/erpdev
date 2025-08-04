# Setup Guide for MyStartup Website

This guide will walk you through setting up the MyStartup Django website project.

## 1. Setup Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

## 2. Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt
```

## 3. Project Setup

```bash
# Create the database
python manage.py migrate

# Create a superuser (admin)
python manage.py createsuperuser
```

## 4. Create Media Directories

```bash
# Create directories for uploaded files
mkdir -p media/blog
mkdir -p media/portfolio
mkdir -p media/testimonials
mkdir -p media/team
mkdir -p media/partners
```

## 5. Collect Static Files

```bash
# Collect static files
python manage.py collectstatic
```

## 6. Run Development Server

```bash
# Start the development server
python manage.py runserver
```

Visit http://127.0.0.1:8000/ to view the website and http://127.0.0.1:8000/admin/ to access the admin panel.

## 7. Adding Content

1. Log in to the admin panel with your superuser credentials
2. Add some categories
3. Add services, portfolio items, blog posts, FAQs, etc.
4. Upload images for portfolio items, blog posts, team members, etc.

## 8. Setting Up Your Images

For the website to look like the templates, you'll need to add some placeholder images:

### Required Images in static/website/img/:
- hero-bg.jpg - Background image for hero section
- hero-illustration.svg - Illustration for hero section
- about-image.jpg - Image for about section
- portfolio-1.jpg, portfolio-2.jpg, portfolio-3.jpg - Portfolio preview images
- blog-1.jpg, blog-2.jpg, blog-3.jpg - Blog preview images
- blog-placeholder.jpg - Default image for blog posts
- client-1.jpg, client-2.jpg, client-3.jpg - Testimonial client images
- partner-1.png through partner-6.png - Partner logos

## 9. Production Deployment

For production deployment:

1. Update `settings.py`:
   - Set `DEBUG = False`
   - Update `ALLOWED_HOSTS`
   - Configure a production database
   - Set up proper email settings
   - Configure static and media file storage

2. Set up a web server like Nginx or Apache with Gunicorn or uWSGI.

3. Use a production-ready database like PostgreSQL.

4. Set up proper media file storage (e.g., Amazon S3).

5. Configure HTTPS using a certificate from Let's Encrypt.

## 10. Regular Maintenance

- Keep Django and other dependencies updated
- Regularly backup your database
- Monitor your site for errors and performance issues
- Keep your content fresh and up-to-date
