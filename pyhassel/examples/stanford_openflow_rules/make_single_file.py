import os

folder = os.getcwd()


of = open('stanford_openflow_rules.py', 'w')

fnames = []

for file in os.listdir(folder):
    if file[-3:] != '.of': continue
    name = file[:-3]
    fnames.append(name)
    full = os.path.join(folder, file)
    f = open(full, 'r')
    contents = f.read()
    #of.write()
    of.write(name + ' = ')
    of.write(contents.replace('null', 'None'))
    of.write('\n')
    f.close()

of.write('\nall_rules = {')
for name in fnames:
    of.write("'" + name + "': " + name + ", ")
of.write("}\n")
of.close()

