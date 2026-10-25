balance = 50000
while True:
    print("1.balance check\n2.deposit amount\n3.withdraw amount\n4.exit:")
    choice = int(input("enter (1,2,3,4):"))
    if choice == 1:
        
        print("your balance is:", balance)
    elif choice == 2:
        deposit = int(input("enter your deposit amount:"))
        if deposit <= 0:
            print("invalid deposit amount please enter correct amount")
        else:
            balance = balance+deposit
            print("deposited_successfully.\nyour current balance is:",balance)

    elif choice==3:
        withdrawl=int(input("enter withdrawl amount:"))
        if withdrawl>balance:
            print("insufficient problem")
        elif withdrawl<=0:
            print("invalid")
        else:
            balance=balance-withdrawl    
            print("withdrawl_successfuly\nyour current balance is:",balance)
    elif choice==4:
        print("thank you!")
        break
    else:
        print("invalid choice")

