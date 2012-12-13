import sys, random
import Queue
import math
import time
from statsbuddy import StatsBuddy


sys.path.append('pyhassel/config_parser')
sys.path.append('pyhassel')


from networksimulator import NetworkFlowruleModel, pad_to_header_length, simple_port_forward_rule
from headerspace.tf import *




# our sole random number generator
rand = random.Random()







class TestNetwork2(object):
    '''
    This network consists of a bunch of complete graphs of switches, patched together by particular
    The switches are named 0...switchcount-1, and the clients are pairs from (0....switchcount-1)x(0...clientsperswitch-1)
    There are 2*(switchcount + switchcount*clientsperswitch) unidirectional ports
    The packet headers are full wildcards.
    '''
    def __init__(self, switchcount = 5, clientsperswitch = 2, minport=0, minswitch=0, numhubs=2):
        if switchcount <= 2: raise Exception('You should use more than 2 switches. Whaddaya, crazy?')

        self.hubs = []

        minport = 0
        for i in range(numhubs):
            minswitch = i * switchcount
            newhub = TestNetwork1( switchcount = switchcount, clientsperswitch = clientsperswitch, minport=minport, minswitch=minswitch)
            self.hubs.append(newhub)
            minport += (newhub.maxport + 1)
        


        print 'Example Network 2 built with', numhubs, 'hubs,' , switchcount, 'switches and', clientsperswitch, 'clients per switch...'
        
        

    def required_rules(self):


    

    def ports_iter(self):
        ''' Iterate over the ports in this network, given as pairs (source, 
        destination), where each element of this pair is either a switch or a client'''

        # first, enumerate the ports from clients to switches and vice versa
        for (s, c) in self.client_iter():
            yield ((s,c), s) # port from client to switch
            yield (s, (s,c)) # port from switch to client
        # complete graph
        for s1 in self.switch_iter():
            for s2 in self.switch_iter():
                if s2 == s1: continue
                yield (s1, s2)

    def in_ports(self, s):
        '''Iterate over the ports that have switch s as their destination'''
        # the switches we neighbour
        for s2 in self.switch_iter():
            if s == s2: continue # no port to ourself
            yield (s2, s)
        # the clients we neighbour
        for c in range(self.clientsperswitch):
            yield ((s, c), s)

    def out_ports(self, s):
        '''Iterate over the ports that have switch s as their source'''
        for (a, b) in self.in_ports(s): 
            # this works because all links are bidirecional, so all all in_ports have a corresponding out_port
            yield (b, a) 

    def in_portnums(self, s):
        '''Iterate the encoded port numbers for the ports connected into switch s'''
        for port in self.in_ports(s):
            yield self.port_to_portnum[port]

    def out_portnums(self, s):
        '''Iterate the encoded port numbers for the ports connected into switch s'''
        for port in self.out_ports(s):
            yield self.port_to_portnum[port]

    def switch_iter(self):
        ''' Iterate over the switches in this network'''
        for i in range(self.minswitch, self.minswitch + self.switchcount):
            yield i

    def client_iter(self):
        ''' Iterate over the clients in this network'''
        for a in self.switch_iter():
            for b in range(self.clientsperswitch):
                yield (a,b)
        
    """def rules(self):
        ''' 
        For every clients, we add rules that cause packets with that client's 
        address to be sent in the correct direction between the switches until 
        they arrive at the destination
        '''
        for (s, c) in self.client_iter():
            headerstring = self.client_to_bitstring_address((s,c))
            for sw in self.switch_iter():
                in_ports = list(self.in_portnums(sw)) # rules will always be for all of our inports
                if s == sw: # packet is destined for a client that sw is already directly connected to
                    out_ports = [self.port_to_portnum[(sw, (s,c))]] # the port connecting s to (s,c)
                else: # need to send it to another switch
                    # we need to decide whether we go clockwise or counterclockwise
                    # if we need to do less than half the circumference of the ring clockwise, go clockwise
                    if (s - sw) % self.switchcount < self.switchcount/2: dir = 1 
                    else: dir = -1
                    out_ports = [self.port_to_portnum[(sw, (sw + dir) % self.switchcount)]]

                rule = simple_port_forward_rule(in_ports, out_ports, wildcard=headerstring)
                if out_ports[0] in in_ports:
                    print ((s,c), sw), out_ports
                yield rule
       """


    '''
    def get_network_model(self):
        n = NetworkFlowruleModel()
        for rule in self.rules():
            (rnum, trace) = n.install_flow_rule(rule)
            if trace: print NetworkFlowruleModel.explain(trace)
        return n
'''


    def get_random_rule(self, min_in, max_in, min_out, max_out):
        # pick random switch
        s = rand.randint(self.minswitch, self.minswitch + self.switchcount - 1)
        ins = randomsubset(self.in_portnums(s), min_in, max_in)
        outs = randomsubset(self.out_portnums(s), min_out, max_out)
        
        rule = simple_port_forward_rule(ins, outs)
        
        return rule




def randomsubset(lis, min, max):
    lis = list(lis)
    if max > len(lis): raise Exception('List too small to take max ' + str(max) + ' elements from.')
    ret = []
    for _ in range(rand.randint(min, max)):
        i = rand.randint(0, len(lis) - 1)
        ret.append(lis[i])
        del lis[i]
    return ret




def runstuff():
    NUM_SWITCHES = 20 # total number of switches in the complete graph of switch-port connectivity
    NUM_CLIENTS = 2 # number of clients on every switch. large numbers will decrease the size of sccs, because 
                    # forwarding to clients is always safe; not part of a loop.
    RULES_PER_ROUND = 350 # number of rule installs to do between gathering time statistics.
    MAX_TOTAL_RULES_INSTALLED = 450 # number of total rules to maintain in the network model, so 
                                    # that as more than these come in, we evict the oldest ones.
    TOTAL_RULE_INSTALLATIONS_BEFORE_HALT = 350 # halt after this many total rule installations.
    SHOW_TRACE = False # should we show the trace when loops are detected? This can get hectic.
    MIN_IN = 1 # minininum number of in_ports to be used in random rules.
    MAX_IN = 3 # etc.
    MIN_OUT = 1
    MAX_OUT = 2



    # the network that we'kll use to generate random valid rules
    net = TestNetwork1(NUM_SWITCHES, NUM_CLIENTS, minswitch=5555, minport=100001)

    # our model
    n = NetworkFlowruleModel() 

    # track the flow install rate in this
    timestats = StatsBuddy()
    total_installed = 0

    # track the rules in place in our NetworkFlowruleModel so we can evict them
    q = Queue.Queue() 

    while True:
        #start a timer
        t1 = time.time()

        # do some rule installations
        for r in xrange(RULES_PER_ROUND):
            if q.qsize() > MAX_TOTAL_RULES_INSTALLED:
                droprule = q.get() # get the number of the rule that's over the limit
                n.drop_flow_rule(droprule) # kill the rule
            rule = net.get_random_rule(MIN_IN, MAX_IN, MIN_OUT, MAX_OUT)
            (rnum, trace) = n.install_flow_rule(rule)
            if SHOW_TRACE and trace: NetworkFlowruleModel.explain(trace)
            q.put(rnum)
            total_installed += 1

        t2 = time.time()

        # NOTE: linux might report this in ms instead of seconds, I think, 
        # so this might give weird results
        timestats.add(RULES_PER_ROUND/(t2-t1)) 

        # how we eventually halt
        if total_installed >= TOTAL_RULE_INSTALLATIONS_BEFORE_HALT: break

        

    print timestats, 'are stats for the number of rule installs and evictions per second.'
    print n.sccsizestats, 'are stats for the average scc size of installed rules.'

    return

    


if __name__ == '__main__':
    runstuff()