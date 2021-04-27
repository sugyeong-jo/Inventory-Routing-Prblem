
import os
import xlrd
from scipy import spatial
from mip import Model, xsum, minimize, BINARY, INTEGER

import pandas as pd

def calculate_dist(x1, x2):
    eudistance = spatial.distance.euclidean(x1, x2)
    return(eudistance)

book = xlrd.open_workbook(os.path.join("DATA.xlsx"))

V = []            # its a set of supplier and Customer,supplier at 1 and remaining are the Customers
cij = {}          # it represents cost of transportation to travel between locations i and j at non-negative cost cij
h = {}            # per period unit inventory holding cost hi
C = {}            # A maximum inventory level Ci is also associated with each customer i belongs to V_Dash
K = ['V1']        # No of Fleets now only one vehicle is used 'V1'
T = [1, 2, 3]     # Let T denote the set of time periods
r = {}            # rit units are consumed at customer i belongs to V_dash
Iit_1 = {}        # an initial inventory level Ii0 are associated with each node
x = {}            # x is set of  x Co-ordinate of Nodes belongs to N
y = {}            # y is set of  y Co-ordinate of Nodes belongs to N
x1 = {}
x2 = {}

sh = book.sheet_by_name("abs1n10")
Q = sh.cell_value(1, 8)  # Fleet Capacity

i = 1
while True:
    try:
        sp = int(sh.cell_value(i, 0))
        V.append(sp)
        x[sp] = sh.cell_value(i, 1)
        y[sp] = sh.cell_value(i, 2)
        Iit_1[sp] = sh.cell_value(i, 3)
        C[sp] = sh.cell_value(i, 4)
        r[sp] = sh.cell_value(i, 6)
        h[sp] = sh.cell_value(i, 7)
        i = i + 1
    except IndexError:
        break
# V_Dash:-
V_dash = V[1:]

# Calculation of cij[i,j] matrix:

for i in V:
    x1[i] = (x[i], y[i])
    for j in V:
        x2[j] = (x[j], y[j])
        cij[i, j] = int(round(calculate_dist(x1[i], x2[j])))

print(f'V : {V}')
print(f'V_dash : {V_dash}')
print(f'Iit_1 : {Iit_1}')
print(f'r : {r}')
print(f'cij : {cij}')

# " Model Formulation "
m = Model("Basic Model Of Inventory Routing Problem")

"""
The variable xijkt represents the number of time
the edge (i,j) belongs to E is traversed
by vehicle k in the time period t
"""
xijkt = {
    (i, j, k, t): m.add_var(var_type=INTEGER, name="x_%s,%s,%s,%s" % (i, j, k, t))
    for i in V for j in V for k in K for t in T
    }
"""
The variable Iit used to indicate the inventory level at Node i belongs to V
at the end of time period t
"""
Iit = {
    (i, t): m.add_var(name="I_%s,%s" % (i, t))
    for i in V for t in T
    }
"""
The variable qikt represents the quantity delivered to customer i
belongs to V_Dash
"""
qikt = {
    (i, k, t): m.add_var(name="q_%s,%s,%s" % (i, k, t))
    for i in V for k in K for t in T
    }

Cikt = {
    (i, k, t): m.add_var(name="c_%s,%s,%s" % (i, k, t))
    for i in V for k in K for t in T
    }

# Constraint 16:-
"""
The variable yikt is a binary variable 1 if node i belongs to V is visited
at time period t belongs T by vehicle v
"""
yikt = {
    (i, k, t): m.add_var(var_type=BINARY, name="y_%s,%s,%s" % (i, k, t))
    for i in V for k in K for t in T
    }

# Constraint 1:-
"""
The objective function (1) calls for
the minimization of the total operational cost,
that is the sum of the inventory costs at the depot,
inventory costs at the customers, and costs of the routes over
the time horizon.
"""
m.objective = minimize(
    xsum(h[i]*Iit_1[i] for i in V) +
    xsum(h[i]*Iit[i, t] for i in V for t in T) +
    xsum(cij[i, j]*xijkt[i, j, k, t] for i in V for j in V for k in K for t in T)
    )

"""
Constraints (2)–(6) determine the evolution of
the inventory level over time and force,
the absence of stockout situations at the supplier and at customers.
"""
# Constraint 2:-
for t in T:
    if t == 1:
        m += ((Iit_1[1] + r[1] - xsum(qikt[i, k, t] for i in V_dash for k in K)) == Iit[1, t])
    else:
        m += ((Iit[1, t-1] + r[1] - xsum(qikt[i, k, t] for i in V_dash for k in K)) == Iit[1, t])

# Constraint 4:-
for i in V_dash:
    for t in T:
        if t == 1:
            m += (Iit_1[i] + xsum(qikt[i, k, t] for k in K) - r[i] == Iit[i, t])
        else:
            m += (Iit[i, t-1] + xsum(qikt[i, k, t] for k in K) - r[i] == Iit[i, t])

# Constraint 5:-
for i in V:
    for t in T:
        m += (Iit[i, t] >= 0)

# Constraint 6:-
for i in V:
    for t in T:
        m += (Iit[i, t] <= C[i])

"""
Constraints (7)–(9) ensure
the OU policy requirements imposing that, if a customer is visited, 
the quantity delivered is such that the maximum inventory level is reached.
"""
# Constraint 7:-
for i in V_dash:
    for t in T:
        if t == 1:
            m += (xsum(qikt[i, k, t] for k in K) <= C[i] - Iit_1[i])
        else:
            m += (xsum(qikt[i, k, t] for k in K) <= C[i] - Iit[i, t-1])

# Constraint 8:-
for i in V_dash:
    for k in K:
        for t in T:
            if t == 1:
                m += (qikt[i, k, t] >= C[i]*yikt[i, k, t] - Iit_1[i])
            else:
                m += (qikt[i, k, t] >= C[i]*yikt[i, k, t] - Iit[i, t-1])

# Constraint 9:-
for i in V_dash:
    for k in K:
        for t in T:
            m += (qikt[i, k, t] <= C[i]*yikt[i, k, t])

"""
Constraints (10) are the vehicle capacity constraints.             
constraints: These constraints guarantee that for each time t e ET,
a feasible route is determined to visit all retailers served at time t.
They can be for mulated as follows:
    (a) If at least one retailer s e V' is visited at time t,
    then the route traveled at time t has to "visit" the supplier.
    Let yot be a binary variable equal to one if the supplier is visited at time t 
    and zero otherwise; then,
"""
# Constraint 10:-
for k in K:
    for t in T:
        m += (xsum(qikt[i, k, t] for i in V_dash) <= Q*yikt[1, k, t])

"""
Constraints (11)–(15) are the routing constraints.
Constraints (11_0) impose to visit each customer
at most once in each time period,
constraints (11) are the degree constraints for each node and
each vehicle in each time period,
"""
# Constraint 11_0:-
for i in V_dash:
    for t in T:
        m += (xsum(yikt[i, k, t] for k in K) <= 1)

# Constraint 11:-
for i in V:
    for k in K:
        for t in T:
            m += (xsum(xijkt[i, j, k, t] for j in V if j != i) == yikt[i, k, t])
            m += (xsum(xijkt[j, i, k, t] for j in V if i != j) == yikt[i, k, t])

# Constraint 12:-
for i in V_dash:
    for t in T:
        for k in K:
            for j in V_dash:
                if i != j:
                    m += (xsum(xijkt[i, j, k, t] for j in V_dash for i in V_dash) <= \
                          xsum(yikt[i, k, t] for i in V_dash) - yikt[i, k, t])
            
# Constraint 13:-
for i in V_dash:
    for k in K:
        for t in T:
            m += (qikt[i, k, t] >= 0)

# Constraint 14 & 15:-
for j in V:
    for k in K:
        for t in T:
            for i in V:
                if i == 1:
                    m += (xijkt[i, j, k, t] <= 2)
                else:
                    m += (xijkt[i, j, k, t] <= 1)
# """
# [Subtour Elimination Constraint]
# Constraint (11) are the SECs for each vehicle route and each time period.
# Note that SECs (11) are stronger than those with right-hand side equal to |S| − 1.
# If we remove constraints (5) from model (k−A−ou),
# the resulting model (k−A−ml) applies for the ML policy.
# """
# # Constraint 11:-
# for i in V_dash:
#     for t in T:
#         for k in K:
#             for j in V:
#                 if i != j:
#                     m += ((Cikt[i, k, t] - Cikt[j, k, t] + Q*xijkt[i, j, k, t]) <= Q - qikt[i, k, t])
# for i in V_dash:
#     for t in T:
#         for k in K:
#             m += (Cikt[i, k, t] <= Q)
#             m += (Cikt[i, k, t] >= qikt[i, k, t])

m.write('MTZ.lp')
m.optimize(max_seconds=600)

solution = []
for i in V:
    for j in V:
        for k in K:
            for t in T:
                solution.append([xijkt[i, j, k, t].name, xijkt[i, j, k, t].x])
                solution.append([Iit[i, t].name, Iit[i, t].x])
                solution.append([qikt[i, k, t].name, qikt[i, k, t].x])
                solution.append([Cikt[i, k, t].name, Cikt[i, k, t].x])
                solution.append([yikt[i, k, t].name, yikt[i, k, t].x])

solution = pd.DataFrame(
    solution,
    columns=['variable', 'solution'])
solution.sort_values(['variable', 'solution'], inplace=True)
solution.drop_duplicates().to_csv('solution.csv', index=False)
print(f'Objective value is : {m.objective_value}')

solution = pd.read_csv('solution.csv')
solution[solution['solution']>0]