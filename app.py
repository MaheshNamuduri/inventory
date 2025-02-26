from flask import Flask, render_template, request, redirect, jsonify, Response
import json
import os
from datetime import datetime, timedelta
import pdfkit

app = Flask(__name__)

INVENTORY_FILE = "inventory.json"

# Load inventory from JSON
def load_inventory():
    try:
        if not os.path.exists(INVENTORY_FILE):
            return []
        with open(INVENTORY_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading inventory: {e}")
        return []

# Save inventory to JSON
def save_inventory(inventory):
    try:
        with open(INVENTORY_FILE, "w") as f:
            json.dump(inventory, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving inventory: {e}")
        return False

# Home route
@app.route("/", methods=["GET", "POST"])
def index():
    inventory = load_inventory()
    total_sales = sum(item["total_sold"] for item in inventory)
    
    if request.method == "POST":
        try:
            name = request.form.get("name")
            stock = int(request.form.get("stock"))
            price = float(request.form.get("price"))
            
            if not name or stock < 0 or price < 0:
                return render_template("index.html", inventory=inventory, total_sales=total_sales, error="Invalid input")
            
            new_item = {
                "id": max([item["id"] for item in inventory], default=0) + 1,
                "name": name,
                "stock": stock,
                "remaining_stock": stock,
                "price": price,
                "total_sold": 0
            }
            inventory.append(new_item)
            if save_inventory(inventory):
                return redirect("/")
            return render_template("index.html", inventory=inventory, total_sales=total_sales, error="Failed to save item")
        except ValueError:
            return render_template("index.html", inventory=inventory, total_sales=total_sales, error="Invalid number format")
    
    return render_template("index.html", inventory=inventory, total_sales=total_sales)

# Search route
@app.route("/search", methods=["GET"])
def search_items():
    query = request.args.get("query", "").lower()
    inventory = load_inventory()
    
    if not query:
        return jsonify({"success": True, "items": inventory})
    
    filtered_items = [
        item for item in inventory 
        if query in item["name"].lower()
    ]
    
    return jsonify({
        "success": True,
        "items": filtered_items
    })

# Sell an item
@app.route("/sell/<int:item_id>", methods=["POST"])
def sell_item(item_id):
    inventory = load_inventory()
    for item in inventory:
        if item["id"] == item_id and item["remaining_stock"] > 0:
            item["remaining_stock"] -= 1
            item["total_sold"] += item["price"]
            if save_inventory(inventory):
                return jsonify({
                    "success": True,
                    "remaining_stock": item["remaining_stock"],
                    "total_sold": item["total_sold"]
                })
            return jsonify({"success": False, "message": "Failed to save changes"})
    return jsonify({"success": False, "message": "Item not found or out of stock"})

# Update price
@app.route("/update_price/<int:item_id>", methods=["POST"])
def update_price(item_id):
    inventory = load_inventory()
    new_price = request.form.get("price")
    try:
        new_price = float(new_price)
        if new_price < 0:
            return jsonify({"success": False, "message": "Price cannot be negative"})
        for item in inventory:
            if item["id"] == item_id:
                item["price"] = new_price
                if save_inventory(inventory):
                    return jsonify({"success": True, "new_price": item["price"]})
                return jsonify({"success": False, "message": "Failed to save changes"})
        return jsonify({"success": False, "message": "Item not found"})
    except ValueError:
        return jsonify({"success": False, "message": "Invalid price value"})

# Remove an item
@app.route("/remove/<int:item_id>", methods=["POST"])
def remove_item(item_id):
    inventory = load_inventory()
    initial_length = len(inventory)
    inventory = [item for item in inventory if item["id"] != item_id]
    
    if len(inventory) < initial_length:
        if save_inventory(inventory):
            return jsonify({"success": True, "message": "Item removed successfully"})
        return jsonify({"success": False, "message": "Failed to save changes"})
    return jsonify({"success": False, "message": "Item not found"})

# Generate Invoice
@app.route("/invoice", methods=["GET"])
def invoice():
    inventory = load_inventory()
    items = [
        {
            "name": item["name"],
            "quantity": item["stock"] - item["remaining_stock"],
            "price": item["price"],
            "total": item["total_sold"]
        }
        for item in inventory if item["total_sold"] > 0
    ]
    invoice_data = {
        "invoice_number": f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "invoice_date": datetime.now().strftime("%Y-%m-%d"),
        "invoice_due_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-d"),
        "supplier_name": "Your Business Name",
        "supplier_contact": "your@email.com",
        "customer_name": "John Doe",
        "customer_contact": "johndoe@email.com",
        "shipping_address": "123 Main Street, City, Country",
        "delivery_address": "789 Warehouse Lane, City, Country",
        "items": items,
        "subtotal": sum(item["total"] for item in items),
        "taxes": round(sum(item["total"] for item in items) * 0.10, 2),
        "total_due": round(sum(item["total"] for item in items) * 1.10, 2),
        "payment_terms": "Due within 14 days. Pay via Bank Transfer."
    }
    return render_template("invoice.html", **invoice_data)

# Update Invoice
@app.route("/update_invoice", methods=["POST"])
def update_invoice():
    updated_items = []
    names = request.form.getlist("item_name[]")
    quantities = request.form.getlist("item_quantity[]")
    prices = request.form.getlist("item_price[]")

    for i in range(len(names)):
        quantity = int(quantities[i]) if quantities[i] else 0
        price = float(prices[i]) if prices[i] else 0.0
        updated_items.append({
            "name": names[i],
            "quantity": quantity,
            "price": price,
            "total": quantity * price
        })
    
    subtotal = sum(item["total"] for item in updated_items)
    taxes = round(subtotal * 0.10, 2)
    total_due = round(subtotal * 1.10, 2)

    invoice_data = {
        "invoice_number": request.form["invoice_number"],
        "invoice_date": request.form["invoice_date"],
        "invoice_due_date": request.form["invoice_due_date"],
        "supplier_name": request.form["supplier_name"],
        "supplier_contact": request.form["supplier_contact"],
        "customer_name": request.form["customer_name"],
        "customer_contact": request.form["customer_contact"],
        "shipping_address": request.form["shipping_address"],
        "delivery_address": request.form["delivery_address"],
        "items": updated_items,
        "subtotal": subtotal,
        "taxes": taxes,
        "total_due": total_due,
        "payment_terms": request.form["payment_terms"]
    }
    return render_template("invoice.html", **invoice_data)

# Download Invoice as PDF
@app.route("/download_invoice", methods=["POST"])
def download_invoice():
    updated_items = []
    names = request.form.getlist("item_name[]")
    quantities = request.form.getlist("item_quantity[]")
    prices = request.form.getlist("item_price[]")

    for i in range(len(names)):
        quantity = int(quantities[i]) if quantities[i] else 0
        price = float(prices[i]) if prices[i] else 0.0
        updated_items.append({
            "name": names[i],
            "quantity": quantity,
            "price": price,
            "total": quantity * price
        })
    
    subtotal = sum(item["total"] for item in updated_items)
    taxes = round(subtotal * 0.10, 2)
    total_due = round(subtotal * 1.10, 2)

    logo_path = os.path.abspath(os.path.join(app.root_path, 'static', 'inventory_logo.png'))
    print(f"Logo path: {logo_path}")

    invoice_data = {
        "invoice_number": request.form["invoice_number"],
        "invoice_date": request.form["invoice_date"],
        "invoice_due_date": request.form["invoice_due_date"],
        "supplier_name": request.form["supplier_name"],
        "supplier_contact": request.form["supplier_contact"],
        "customer_name": request.form["customer_name"],
        "customer_contact": request.form["customer_contact"],
        "shipping_address": request.form["shipping_address"],
        "delivery_address": request.form["delivery_address"],
        "items": updated_items,
        "subtotal": subtotal,
        "taxes": taxes,
        "total_due": total_due,
        "payment_terms": request.form["payment_terms"],
        "logo_path": logo_path
    }

    html_string = render_template("invoice_pdf.html", **invoice_data)
    print(f"HTML content (first 500 chars): {html_string[:500]}")

    try:
        pdf = pdfkit.from_string(
            html_string,
            False,
            options={
                'encoding': 'UTF-8',
                'quiet': '',
                'enable-local-file-access': ''
            }
        )
    except Exception as e:
        print(f"wkhtmltopdf error: {str(e)}")
        return f"PDF generation failed: {str(e)}", 500

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename=invoice_{invoice_data['invoice_number']}.pdf"}
    )

if __name__ == "__main__":
    app.run(debug=True)