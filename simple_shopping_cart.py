item = []

while len(item) < 5:
    product_price = int(input(f"enter product amount {len(item) + 1}: "))
    
    if product_price <= 0:
        print("invalid amount. Please enter a positive number.")
    else:
        item.append(product_price)

total_bill = sum(item)
highest = max(item)
lowest = min(item)

print("Summary ")
print("total bill:", total_bill)
print("highest price:", highest)
print("lowest price:", lowest)

if total_bill >= 5000:
    discount = total_bill * 0.10
    final_bill = total_bill - discount
    print("discount applied: ", discount)
    print("final bill:", final_bill)
else:
    print("discount: 0")
    print("final bill:", total_bill)
