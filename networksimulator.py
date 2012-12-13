import sys
# the mock-0.3.1 dir contains testcase.py, testutils.py & mock.py
sys.path.append('pyhassel/config_parser')
sys.path.append('pyhassel')


#foo = imp.load_source('module.name', '/path/to/file.py')

from headerspace import *
from headerspace.tf import *
from headerspace.hs import *
from dynamicscc import DynamicSCC
from statsbuddy import StatsBuddy, Buckets

from collections import defaultdict
from Queue import Queue


# this is the length of header that all rules will be expecting and requiring
HEADER_LENGTH = 24 # this should be a multiple of 4
ALLMASK = "x" * (HEADER_LENGTH)
ONEMASK = "1" * (HEADER_LENGTH)
ZEROMASK = "0" * (HEADER_LENGTH)
HEADERSPACE_ALL = headerspace(HEADER_LENGTH / 4)
HEADERSPACE_ALL.add_hs(hs_string_to_byte_array(ALLMASK))


def pad_to_header_length(string=None, num=None, size=None):
    '''
    Encode string or num into a binary string of length HEADER_LENGTH.
    The size parameter is used for input num, to indicate that the input 
    number should occupy the first 'size' bits of the resulting encoded string
    '''
    if string == None:
        assert num is not None and size is not None
        string = bin(num)[2:]
        assert len(string) <= size
        string = string.rjust(size, '0') # pad so the binary destination description is in the right place
    if len(string) > HEADER_LENGTH:
        raise "You should increase HEADER_LENGTH to accomodate bitstrings this long"
    return string.ljust(HEADER_LENGTH, 'x')


class NetworkFlowruleModel(object):
    '''
    Build an object that can tell us whether the ruleset can permit looping in the network.
    Flow rules are to be provided in the form of the result of a call to 
    TF.create_standard_rule(in_ports, match, out_ports, mask, rewrite,file_name,lines)
    where all referenced port numbers refer model distinct unidirectional physical connections
    between switches. This class does not necessarily check that the rules are sane. That 
    is, you can (unsafely) add flow rules that are not physically possible, 
    for instance redirecting packets that arrive on more than one switch or 
    that do not have the in ports and out ports on the same physical router.
    '''
    def __init__(self):
        self.in_port_rules = defaultdict(lambda: [])
        self.out_port_rules = defaultdict(lambda: [])

        self.rulenum_to_rule = {}
        self.rulenum_to_inspace = {}
        self.rulenum_to_outspace = {}
        self.rulenum_to_in_ports = {}
        self.rulenum_to_out_ports = {}

        self.dscc = DynamicSCC()

        # for tracking the number of components in sccs for newly added rules
        self._collect_stats = False
        self.scc_size_stats = StatsBuddy()
        self.scc_buckets = None
        self.edges_stats = StatsBuddy()
        self.loops_detected = 0
        self.loop_detection_calls = 0

        # first installed flow rule will be number 0
        # iterated whenever a flow is installed, so no overlap is possible
        self._r = 0



    def install_flow_rule(self, rule):
        # we use the flow rule number (assigned from 0 as rules are entered) as the vertex
        newrnum = self._r
        self._r += 1

        self.rulenum_to_rule[newrnum] = rule
        
        # update the in/out_port_rules dictionaries ,so we can easily detect 
        # who we have to test for intersection with this rule later
        # HACK. This uses a poorly understood backdoor into the TF class
        # by asking for in/outport_to_rule.keys(), when there may be situations
        # (I'm not sure, OK?) when it doesn't provide the right answers
        inports =  [int(p) for p in rule.inport_to_rule.keys()]
        self.rulenum_to_in_ports[newrnum] = inports
        outports = [int(p) for p in rule.outport_to_rule.keys()]
        self.rulenum_to_out_ports[newrnum] = outports

        for port in inports: self.in_port_rules[port].append(newrnum)
        for port in outports: self.out_port_rules[port].append(newrnum)

        # these are lists of pairs (headerspace, portlist)
        outspace = [item for port in inports for item in rule.T(HEADERSPACE_ALL, port)]
        inspace = [item for port in outports for item in rule.T_inv(HEADERSPACE_ALL, port)]

        self.rulenum_to_inspace[newrnum] = inspace
        self.rulenum_to_outspace[newrnum] = outspace
      
        # add this rule into the dynamic graph structure
        self.dscc.insert_vertices([newrnum])

        # cases where there might be an edge (newrnum, ?) and below, (?, newrnum), since they in/out on the same port
        possible_to_rules = [r for outport in outports for r in self.in_port_rules[outport]]
        possible_from_rules = [r for inport in inports for r in self.out_port_rules[inport]]

        # cases where there is a headerspace intersection in the inputs and outputs
        real_to_rules = filter(lambda r: NetworkFlowruleModel.rule_spaces_intersect(outspace, self.rulenum_to_inspace[r]), possible_to_rules)
        #if len(real_to_rules) > 0: print real_to_rules
        real_from_rules = filter(lambda r: NetworkFlowruleModel.rule_spaces_intersect(inspace, self.rulenum_to_outspace[r]), possible_from_rules)
        #if len(real_from_rules) > 0: print real_from_rules

        # the real edges to insert
        newedges = set([(newrnum, to) for to in real_to_rules])
        newedges.update(set([(frum, newrnum) for frum in real_from_rules]))

        #print "New edges are:", newedges
        
        # add the edges to our SCC detecting graph
        self.dscc.insert_edges(newedges)

        # how big is the scc we're in?
        newscc = self.dscc.getSCC(newrnum)
        sccsize = len(newscc)

        # process SCC statistics
        if self._collect_stats: 
            self.edges_stats.add(len(newedges))
            self.scc_size_stats.add(sccsize) 
            self.scc_buckets.add(sccsize)
        
        if sccsize == 1: 
            return (newrnum, False)

        
        '''
        print newscc, 'is a set of rules that could loop'
        for rnum in newscc:
            print self.rulenum_to_rule[rnum]
            print self.rulenum_to_inspace[rnum]
            print self.rulenum_to_outspace[rnum]
        raise Exception("Quick Break")
        '''

        # return the number of the inserted rule and some info
        info = self.find_loop_in_scc(newscc, newrnum)
        return (newrnum, info)
    ## end install_flow_rule

    def collect_stats(self, bool): 
        '''
        Turn collecting of SCC size statistics on or off
        '''
        self._collect_stats = bool
        # collect scc buckets on the assumption that the current number of rules is about the most we'll see, unless we have none yet
        bmax = len(self.rulenum_to_rule) if len(self.rulenum_to_rule) > 20 else 200
        self.scc_buckets = Buckets(0, bmax)

    def find_loop_in_scc(self, scc, rnum):
        q = Queue()
        # collect stats, it we should be doing so
        if self._collect_stats: self.loop_detection_calls += 1
        # this was set when the rule was added
        initial_spaces = self.rulenum_to_outspace[rnum]

        # queue items look like ([(hs, [ports])], [visited_rules])
        # we start with the full header space on the ports that the rule of interest outputs
        q.put( (initial_spaces, [rnum]) )
        while not q.empty():
            current_places, visited_rules = q.get()

            for space, ports in current_places:
                # sometimes empty spaces can be here. we can ignore them
                if space.is_empty(): continue
                for port in ports:
                    for nextrule in scc:
                        # if the current space routes into another rule in the scc
                        if nextrule in self.in_port_rules[port]:
                            currpath = visited_rules + [nextrule]
                            # process space, port through nextrule
                            out = self.rulenum_to_rule[nextrule].T(space, port)
                            if len(out) == 0: continue
                            # check if we have a loop here
                            if nextrule in visited_rules:
                                # we've visited this rule before, if we have a nonempty header left, we've found a loop
                                for outspace, outports in out:
                                    if not outspace.is_empty():
                                        # collect stats, it we should be doing so
                                        if self._collect_stats: self.loops_detected += 1

                                        # backtrace this, ignoring the other possible loops
                                        original_space = self.backtrace([(outspace, outports)], currpath)

                                        ret = {'rule_path': currpath, 'headers_in': original_space, 'headers_out': [(outspace, outports)]}
                                        return ret
                                        
                                continue
                            # register another node to check
                            q.put( (out, currpath) )
        return False
    ## end find_loop_in_scc

    
    @staticmethod
    def explain(info):
        path = info['rule_path']
        print '---Backtrace shows that packets can loop in your network:'
        for hs, ports in info['headers_in']:
            print '-- Port(s)', ports, 'with headers', hs
        print '-- They take the path of rules', path, 'in a loop.'
        print '-- And are emitted by rule', path[-1], 'at the end of the above loop as:'
        for hs, ports in info['headers_out']:
            print '-- Port(s)', ports, 'with headers', hs
        print '-- Other packets may also loop.'


    def backtrace(self, hspaces, rulelist):
        '''
        Trace the behaviour of hspace travelling through rulelist _in reverse_,
        returning the original set of (hspace,ports) that could have caused the
        hspaces arg to have been emitted.
        '''        
        for rnum in reversed(rulelist):
            # trace hspace backwards through rule rnum
            rule = self.rulenum_to_rule[rnum]
            nextgen = []
            for (hspace, ports) in hspaces:
                for port in ports:
                    nextgen.extend(rule.T_inv(hspace, port))
            hspaces = nextgen
        # hspaces is now the original ingress packets that had eventually 
        # called the original hspaces to be ejected from the last rule in rulelist
        return hspaces
    ## end backtrace


    @staticmethod
    def rule_spaces_intersect(a, b):
        '''
        Detemine whether there is a nonempty intersection between 2 (headerspace, portlist) lists
        '''
        for (hs1, ports1) in a:
            sports1 = set(ports1)
            for (hs2, ports2) in b:
                sports2 = set(ports2)
                if len(sports1.intersection(sports2)) == 0: continue
                if not hs1.copy_intersect(hs2).is_empty(): 
                    return True
        return False



    def drop_flow_rule(self, rnum):
        '''Update all of the stored data to a state as if rule rnum never existed'''
        rule = self.rulenum_to_rule[rnum]
        del self.rulenum_to_rule[rnum]
        for port in self.rulenum_to_in_ports[rnum]: self.in_port_rules[port].remove(rnum)
        for port in self.rulenum_to_out_ports[rnum]: self.out_port_rules[port].remove(rnum)
        del self.rulenum_to_in_ports[rnum]
        del self.rulenum_to_out_ports[rnum]
        del self.rulenum_to_inspace[rnum]
        del self.rulenum_to_outspace[rnum]
        self.dscc.delete_vertex(rnum)


    
''' NOTES:
TF.create_standard_rule(in_ports, match, out_ports, mask, rewrite,file_name,lines)
TF.standard_rule_to_string(std_rule)

'''


def simple_port_forward_rule(in_ports, out_ports, wildcard=ALLMASK):    
    ''' Make a rule that causes all traffic on in_ports to be repeated through all of the out_ports.'''
    ret = TF(HEADER_LENGTH / 4)
    rule = TF.create_standard_rule(in_ports, wildcard, out_ports, ONEMASK, ZEROMASK, '', [])
    #rule = TF.create_standard_rule(in_ports, wildcard, out_ports, ONEMASK, ONEMASK, '', [])
    ret.add_rewrite_rule(rule)
    return ret





#file='''./pyhassel/examples/run_reachability_su_bb.py'''



    
    



if __name__ == '__main__':
    # testing
    
    n = NetworkFlowruleModel()

    # build a ring that stupidly forwards all packets around the loop
    size = 5
    for i in range(size):        
        r, trace = n.install_flow_rule(simple_port_forward_rule([i], [(i+1) % size]))

        # this is the only line that would invoke a print call
        if trace: NetworkFlowruleModel.explain(trace)




