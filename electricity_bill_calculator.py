# Take units consumed as input.
unit=int(input("hhow much units you consumed: "))
# if unit less than 0
if unit <=0:
    print("invalid input")
# If units are ≤ 100, charge Rs. 10 per unit.
elif unit <=100:
    print(unit*10)
# If units are 101–200, first 100 units cost Rs. 10 each, and remaining units cost Rs. 15 each.
elif unit<=200:
    print((unit-100)*15+(100*10))
# If units are 201–300, first 200 units are charged according to the above slabs, and remaining units cost Rs. 20 each.
elif unit<=300:
    print((unit-200)*20+(unit-100)*15+(100*10))

# If units are above 300, first 300 units are charged according to the above slabs, and remaining units cost Rs. 25 each.
else:
     print((unit-300)*25+(unit-200)*20+(unit-100)*15+(100*10))
