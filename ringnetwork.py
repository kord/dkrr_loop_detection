import sys
# the mock-0.3.1 dir contains testcase.py, testutils.py & mock.py
sys.path.append('pyhassel/config_parser')
sys.path.append('pyhassel')


from networksimulator import NetworkFlowruleModel, pad_to_header_length, simple_port_forward_rule, HEADER_LENGTH
from headerspace.tf import *

class RingNetwork(object):
    '''
    This network consists of a ring of switches, each with a certain number of clients attached to them.
    The switches are named 0...switchcount-1, and the clients are pairs from (0....switchcount-1)x(0...clientsperswitch-1)
    There are 2*(switchcount + switchcount*clientsperswitch) unidirectional ports
    The packet headers in the model consist of nothing but the destination of the packet. The destination client (a,b) is given by the header bin(a*switchcount+b)
    For every (client,client) pair, we install a flow on the appropriate switch that directs 
    '''
    def __init__(self, switchcount = 5, clientsperswitch = 2, ADD_FLAW = False):
        self.switchcount = switchcount
        self.clientsperswitch = clientsperswitch
        self.ADD_FLAW = ADD_FLAW

        import math
        self.destinationlength = int(math.ceil(math.log(switchcount * clientsperswitch, 2)))

        # aliases for ports
        self.portnum_to_port = {}
        self.port_to_portnum = {}
        for (i, port) in enumerate(self.ports_iter()):
            self.portnum_to_port[i] = port
            self.port_to_portnum[port] = i
        #for (i, port) in enumerate(self.ports_iter()):
        #    print self.port_to_portnum[port] 
        

    def client_to_bitstring_address(self, client):
        '''Given a destination, give the wildcard bitstring matching headers destined for that destination'''
        (switch, cnum) = client # unpack
        if switch >= self.switchcount or switch < 0:
            raise Exception("This RingNetwork only has " + str(self.switchcount) + ' switches but you asked for switch #' + str(switch))
        if cnum >= self.clientsperswitch or cnum < 0:
            raise Exception("This RingNetwork only has " + str(self.clientsperswitch) + ' clients per switch but you asked for client #' + str(cnum))

        hostnum = switch * self.clientsperswitch + cnum        
        return pad_to_header_length(num=hostnum, size=self.destinationlength)

    def ports_iter(self):
        ''' Iterate over the ports in this network, given as pairs (source, 
        destination), where each element of this pair is either a switch or a client'''

        # first, enumerate the ports from clients to switches and vice versa
        for (s, c) in self.client_iter():
            yield ((s,c), s) # port from client to switch
            yield (s, (s,c)) # port from switch to client
        for s in self.switch_iter():
            yield (s, (s+1) % self.switchcount)
            yield (s, (s-1) % self.switchcount)

    def in_ports(self, s):
        '''Iterate over the ports that have switch s as their destination'''
        # the switches we neighbour
        yield ((s+1) % self.switchcount, s)
        yield ((s-1) % self.switchcount, s)
        # the clients we neighbour
        for c in range(self.clientsperswitch):
            yield ((s, c), s)

    def in_portnums(self, s):
        '''Iterate the encoded port numbers for the ports connected into switch s'''
        for port in self.in_ports(s):
            yield self.port_to_portnum[port]

    def switch_iter(self):
        ''' Iterate over the switches in this network'''
        for i in range(self.switchcount):
            yield i

    def client_iter(self):
        ''' Iterate over the clients in this network'''
        for a in range(self.switchcount):
            for b in range(self.clientsperswitch):
                yield (a,b)
        
    def rules(self):
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
        

        if self.ADD_FLAW:
            s,sw,c = 1,2,1
            in_ports = list(self.in_portnums(sw)) # rules will always be for all of our inports
            if s == sw: # packet is destined for a client that sw is already directly connected to
                out_ports = [self.port_to_portnum[(sw, (s,c))]] # the port connecting s to (s,c)
            else: # need to send it to another switch
                # we need to decide whether we go clockwise or counterclockwise
                # if we need to do less than half the circumference of the ring clockwise, go clockwise
                if (s - sw) % self.switchcount < self.switchcount/2: dir = -1 
                else: dir = 1
                out_ports = [self.port_to_portnum[(sw, (sw + dir) % self.switchcount)]]

            rule = simple_port_forward_rule(in_ports, out_ports, wildcard=headerstring)
            if out_ports[0] in in_ports:
                print ((s,c), sw), out_ports
            yield rule


    def get_network_model(self):
        n = NetworkFlowruleModel()
        for rule in self.rules():
            (rnum, trace) = n.install_flow_rule(rule)
            if trace: print NetworkFlowruleModel.explain(trace)
        return n



def runstuff():

    # 11 switches in a ring, each with 2 clients
    net = RingNetwork(11,2, True)
    net.client_to_bitstring_address((2,0))
    n = net.get_network_model()




    return

    


if __name__ == '__main__':
    runstuff()