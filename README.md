# 🧾 InvoxiaGST – GST Billing & Invoice Management System  

A full-stack **E-Commerce & GST Billing Platform** that helps small and medium businesses manage:  
✅ Customer & product records and management  
✅ GST-compliant invoice generation  
✅ Sales history & analytics dashboards 
✅ Monthly and Yearly Stock Details 
✅ PDF invoice export 

This project was developed as part of a **Semester-2 project** to combine **Django concepts, frontend development, database and analytics**.  

---
## 📁 Folder Structure
```bash
🏗️ Root Directory
E-Commerce/
├── manage.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── E-Commerce/                    # Main project configuration
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── accounts/                      # User authentication & management
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
│
├── core/                         # Core functionality
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
│
├── products/                     # Product management
│   └── (empty directory)
│
├── store/                        # Main store functionality
│   ├── analytics.py
│   ├── forms.py
│   ├── manage_products.py
│   ├── middleware.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
│
├── templates/                    # HTML templates
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── customer_login.html
│   ├── customer_register.html
│   ├── products_page.html
│   ├── product_detail.html
│   ├── product_list.html
│   ├── add_product.html
│   ├── update_product.html
│   ├── delete_product.html
│   ├── cart.html
│   ├── order.html
│   ├── order_detail.html
│   ├── my_orders.html
│   ├── payment_success.html
│   ├── analytics_dashboard.html
│   ├── user_analytics_dashboard.html
│   ├── sales_dashboard.html
│   ├── sales_report.html
│   ├── monthly_stock_report.html
│   ├── yearly_stock_summary.html
│   ├── stock_details.html
│   ├── invoice_template.html
│   ├── subscription_history.html
│   ├── plan.html
│   ├── about.html
│   ├── contact.html
│   ├── docs.html
│   ├── data_analysis.html
│   ├── history.html
│   └── error.html
│
├── static/                       # Static files (CSS, JS, images)
│   └── (empty directory)
│
├── media/                        # User-uploaded files
│   └── products/
│       ├── classmate_spiral_notebook.jpeg
│       ├── oreo_buscuit.jpeg
│       ├── aruns_notebook_D2rwnrJ.jpeg
│       └── aruns_notebook.jpeg
│
└── screenshots/                  # Project documentation images
    ├── dashboard.png
    ├── home_page.png
    ├── sales.png
    ├── customer_dashboard.png
    ├── myorders.png
    └── Invoice.png
```

## 🚀 Features  

### 🔐 Authentication & User Management  
- Secure login and signup  
- Each registered user maintains their own store  
- Separate database per registered user  

### 📦 Customer & Product Management  
- Add, update, or delete products  
- Product fields:  
  - Name  
  - GST Rate  
  - Selling Price  
  - Stock availability  

### 🧾 Invoice Management  
- Auto GST calculation (SGST + CGST)  
- Create invoices with multiple products  
- Download invoices as **PDF**  

### 📜 Invoice History & Filters  
- Track sales by **customer** or **date**  
- View history of sold items and stock left  
- Track payment status  

### 📊 Data Analytics Dashboard  
- Monthly & yearly GST collection reports  
- Product-wise sales summaries  
- Top customer insights  

### 📤 Export  
- Export invoices as PDF  

---

## 🛠️ Technology Stack  

**Backend**  
- Python 3.11  
- Django 
- Jinja2 templates  

**Database**
- PostgreSQL

**Frontend**  
- HTML, CSS, Bootstrap , JavaScript 
 

---

## ⚡ Installation & Setup  

1. **Clone the Repository**  
```bash
git clone https://github.com/Tejas132005/E-Commerce-Platform.git
cd E-Commerce-Platform

2. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
source venv/bin/activate   # On Mac/Linux
venv\Scripts\activate      # On Windows

pip install -r requirements.txt

3. Run Database Migrations
```bash
python manage.py migrate

4. Start the Server
```bash
python manage.py runserver

5. Open in browser:
👉 http://127.0.0.1:8000

---

📸 Screenshots

## home page/ dashboard
![Home Page](screenshots/home_page.png)  
![Dashboard](screenshots/dashboard.png)

## Sales
![Sales Dashboard](screenshots/sales.png)

## Customers 
![Customer Dashboard](screenshots/customer_dashboard.png)
![Orders](screenshots/myorders.png)

## Invoice 
![Invoice](screenshots/Invoice.png)

---

👥 Contributors
Tejas Jyoti – Developer

---

📜 License
This project is for educational purposes. You may use and modify it for learning.
