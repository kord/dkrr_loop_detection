import sys, random
import Queue
import math
import time
from statsbuddy import StatsBuddy


sys.path.append('pyhassel/config_parser')
sys.path.append('pyhassel')


from networksimulator import NetworkFlowruleModel, pad_to_header_length, simple_port_forward_rule, HEADER_LENGTH
from headerspace.tf import *




# our sole random number generator
rand = random.Random()







class TestNetwork(object):
    '''
    This network consists of a complete graph of switches, each with a certain number of clients attached to them.
    The switches are named 0...switchcount-1, and the clients are pairs from (0....switchcount-1)x(0...clientsperswitch-1)
    There are 2*(switchcount + switchcount*clientsperswitch) unidirectional ports
    The packet headers are full wildcards.
    '''
    def __init__(self, switchcount = 5, clientsperswitch = 2, minport=0, minswitch=0):
        if switchcount <= 2: raise Exception('You should use more than 2 switches. Whaddaya, crazy?')

        self.minswitch = minswitch
        self.switchcount = switchcount
        self.maxswitch = minswitch + switchcount

        self.clientsperswitch = clientsperswitch

        #self.destinationlength = int(math.ceil(math.log(switchcount * clientsperswitch, 2)))

        # aliases for ports
        self.portnum_to_port = {}
        self.port_to_portnum = {}

        self.minport = minport

        for (i, port) in enumerate(self.ports_iter()):
            self.portnum_to_port[i + minport] = port
            self.port_to_portnum[port] = i + minport
        #for (i, port) in enumerate(self.ports_iter()):
        #    print self.port_to_portnum[port] 

        self.maxport = max(self.portnum_to_port.keys())

        #print 'Example Network built with', switchcount, 'switches and', clientsperswitch, 'clients per switch...'
        
        

    

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
        for i in range(self.minswitch, self.maxswitch):
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
        s = rand.randint(self.minswitch, self.maxswitch - 1)
        ins = randomsubset(self.in_portnums(s), min_in, max_in)
        outs = randomsubset(self.out_portnums(s), min_out, max_out)
        
        rule = simple_port_forward_rule(ins, outs)
        
        return rule




    def get_random_rewrite_rule(self, min_in, max_in, min_out, max_out, min_match_bits, max_match_bits, min_rewrite_bits, max_rewrite_bits):
        # pick random switch
        s = rand.randint(self.minswitch, self.maxswitch - 1)
        in_ports = randomsubset(self.in_portnums(s), min_in, max_in)
        out_ports = randomsubset(self.out_portnums(s), min_out, max_out)
        match = random_wildcard(min_match_bits, max_match_bits)
        mask, rewrite = random_rewrite(min_rewrite_bits, max_rewrite_bits)
        
        tf = TF(HEADER_LENGTH/4)
        rule = TF.create_standard_rule(in_ports, match, out_ports, mask, rewrite, '', [])
        tf.add_rewrite_rule(rule)

        #print tf
        return tf


def random_wildcard(min_match_bits, max_match_bits):
    return random_bitstring(min_match_bits, max_match_bits, 'x', ['0','1'])

def random_rewrite(min_match_bits, max_match_bits):
    mask = random_bitstring(min_match_bits, max_match_bits, '1', ['0'])
    rewrite = []
    for i, char in enumerate(mask):
        if char == '1': 
            rewrite.append('0')
        else: 
            bit = rand.choice(['0','1'])
            rewrite.append(bit)
    return mask, ''.join(rewrite)

    

def random_bitstring(min_match_bits, max_match_bits, default, choices, length=HEADER_LENGTH):
    ret = []
    rands = randomsubset(range(length), min_match_bits, max_match_bits)
    for i in range(length):
        if i in rands:
            randombit = rand.choice(choices)
            ret.append(randombit)
        else:
            ret.append(default)
    return ''.join(ret)


def randomsubset(lis, min, max):
    lis = list(lis)
    if max > len(lis): raise Exception('List too small to take max ' + str(max) + ' elements from.')
    ret = []
    for _ in range(rand.randint(min, max)):
        i = rand.randint(0, len(lis) - 1)
        ret.append(lis[i])
        del lis[i]
    return ret


def RunTest(num_switches, num_clients, steady_state_avg_rules_per_switch, 
                  total_rule_installations_before_halt, 
                  min_in, max_in, min_out, max_out, 
                  min_match_bits=0, max_match_bits=0, min_rewrite_bits=0, max_rewrite_bits=0,
                  show_trace = False, 
                  rewrite_rule_probability = 1.0):
    """
    num_switches: 
        total number of switches in the complete graph of switch-port connectivity
    num_clients: 
        number of clients on every switch. large numbers will decrease the size of sccs, 
        because forwarding to clients is always safe; not part of a loop.
    steady_state_avg_rules_per_switch: 
        The average number of rules to keep in the network per switch before rules are evicted
        The network will gradually be built up to have steady_state_avg_rules_per_switch * num_switches
        and then exist with that steady state number of rules until the total number of rule 
        installations occurs
    total_rule_installations_before_halt: 
        Halt after this many total rule installations. (Will be rounded to a multiple of 20, 
        to make progress reporting cleaner)

    min_in:  
        Minininum number of in_ports to be used in random rules
    max_in: etc.
    min_out: etc.
    max_out: etc.

    show_trace: 
        Should we show the trace when loops are detected? This can get hectic and start spinning the terminal.
    
    min_match_bits: 
        The minimum number of bits to fix as non-'x' in random rewrite rule matchs
    max_match_bits: 
        Max of above
    min_rewrite_bits: 
        The minimum number of bits to explicitly fix randomly as one of 0/1 in output packets
    max_rewrite_bits: 
        Max of above
    """

    # some basic info for our run
    steady_state_rules_in_network = num_switches * steady_state_avg_rules_per_switch
    rules_per_round = total_rule_installations_before_halt / 20
    total_rule_installations_before_halt = rules_per_round * 20

    # eject if params are silly
    if total_rule_installations_before_halt <= steady_state_rules_in_network:
        raise Exception('The given parameters will not permit the network to reach a steady state, so no statistics would be collected. Try decreasing "steady_state_avg_rules_per_switch".')

    # the network that we'll use to generate random valid rules
    net = TestNetwork(num_switches, num_clients)

    # our model
    n = NetworkFlowruleModel() 

    # annotate the parameters
    print 'Parameters for this run are:', (num_switches, num_clients, steady_state_avg_rules_per_switch, 
                                          total_rule_installations_before_halt, 
                                          min_in, max_in, min_out, max_out, 
                                          min_match_bits, max_match_bits, min_rewrite_bits, max_rewrite_bits,
                                          show_trace, rewrite_rule_probability)
    print 'Steady state will have {} rules installed.'.format(steady_state_rules_in_network)

    #start a timer
    test_start_time = time.time()
    steady_state_start_time = None # we'll set this when we reach maximum flow capacity for the network
    total_installed = 0


    # track the rules in place in our NetworkFlowruleModel so we can evict them
    q = Queue.Queue()

    while total_installed < total_rule_installations_before_halt:
        # do some rule installations
        for r in xrange(rules_per_round):
            # drop rules so we don't exceed steady_state_rules_in_network
            if q.qsize() > steady_state_rules_in_network:
                droprule = q.get() # get the number of the rule that's over the limit
                n.drop_flow_rule(droprule) # kill the rule
                if steady_state_start_time is None:
                    n.collect_stats(True)
                    steady_state_start_time = time.time()

            ######################################
            if rand.random() <= rewrite_rule_probability:
                rule = net.get_random_rewrite_rule(min_in, max_in, min_out, max_out, min_match_bits, max_match_bits, min_rewrite_bits, max_rewrite_bits)
            else:
                rule = net.get_random_rule(min_in, max_in, min_out, max_out)
            ######################################

            # put the random flow into our model
            (rnum, trace) = n.install_flow_rule(rule)
            # show detected loop details if desired
            if show_trace and trace: NetworkFlowruleModel.explain(trace)
            q.put(rnum)
            total_installed += 1

        amount_done = 1.0 * total_installed / total_rule_installations_before_halt
        if steady_state_start_time is not None:
            time_in_steady_state = time.time() - steady_state_start_time
            amount_of_steady_state_done = 1.0 * (total_installed - steady_state_rules_in_network) / (total_rule_installations_before_halt - steady_state_rules_in_network)
            expected_steady_state_time_total = time_in_steady_state / amount_of_steady_state_done
            expected_remaining_time = expected_steady_state_time_total * (1.0 - amount_of_steady_state_done)
            print '{:.0%} done. Expected {:.4g}s remaining'.format(amount_done, expected_remaining_time)
        else:
            print '{:.0%} done. Steady state not yet entered...'.format(amount_done)


    test_end_time = time.time()
    total_test_time = test_end_time - test_start_time
    steady_state_total_time = test_end_time - steady_state_start_time

    # show heaps of info about the run
    print
    print 'Overall, {:.5g} rules were installed per second on average.'.format(1.0 * total_rule_installations_before_halt / total_test_time)
    print 'While in steady state, {:.5g} rules were installed per second on average.'.format(1.0 * (total_rule_installations_before_halt - steady_state_rules_in_network) / steady_state_total_time)
    print n.scc_size_stats, 'are the stats for the average SCC size of installed rules.'
    print n.edges_stats, 'are the stats for the average number of graph edges added per installed rule.'
    print 'Loop detection was called for {:.4%} of rule installs'.format(1.0 * n.loop_detection_calls / total_rule_installations_before_halt)
    print 'Loops were detected for {:.4%} of rule installs'.format(1.0 * n.loops_detected / total_rule_installations_before_halt)
    print 'Loops were present for {:.4%} of calls to loop detection'.format(1.0 * n.loops_detected / n.loop_detection_calls)
    
    print n.scc_buckets.graph()



if __name__ == '__main__':
    '''
    NEW ARGUMENT FORMAT:
    def RunTest(num_switches, num_clients, steady_state_avg_rules_per_switch, 
                  total_rule_installations_before_halt, 
                  min_in, max_in, min_out, max_out, 
                  min_match_bits=0, max_match_bits=0, min_rewrite_bits=0, max_rewrite_bits=0,
                  show_trace = False, 
                  rewrite_rule_probability = 1.0):
    '''
    '''
    RunTest(20, 5, 100, 100*20*2, 
            1, 3, 1, 2, 
            rewrite_rule_probability = 0.0)
    
    RunTest(200, 15, 100, 100*200*2, 
            1, 3, 1, 2,
            rewrite_rule_probability = 0.0)

    '''
    #RunTest(20, 5, 100, 100*20*2, # was original line here. use smaller values just to speed things up
    RunTest(20, 2, 80, 100*20*2 , 
            1, 6, 1, 2, 
            15, 20, 1, 4, # without the 1, these will sometimes be forwarding rules, but we now permit those sometimes anyway with rewrite_rule_probability
            rewrite_rule_probability = 0.99)
    '''
    RunTest(200, 15, 100, 100*200*2, 
            1, 3, 1, 2, 
            0, 4, 1, 4, 
            rewrite_rule_probability = 0.99)
    '''
