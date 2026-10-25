student_marks=[]
pass_count=0
fail_count=0
for student in range(5):
    marks=int(input("enter your marks: "))
    if marks<0 or marks>100:
      print("invalid")
    else:
      student_marks.append(marks)
    
      if marks<40:
        print("fail")
        fail_count+=1
      else:
        print("pass")
        pass_count+=1

if len(student_marks)>0:  
   average_marks = sum(student_marks) / len(student_marks)      
   print("student_marks: ",student_marks) 
   print("pass: ",pass_count)
   print("fail: ",fail_count) 
   print("total: ",sum(student_marks))
   print("average_marks: ",average_marks)
   print("maximum: ",max(student_marks))
   print("minimum" ,min(student_marks))
else:
   print("invalid")

