import networkx as nx
import LCA
import sys

class Node:
    def __init__(self, data, parent):
        self.data = data
        if parent == None:
            self.parent = None
        else:
            self.parent = parent
        self.rank = 0
        self.version = 0
        
    def _update_parent(self, newparent):
        self.parent = newparent

    def __str__(self):
        return "-".join([str(self.data), str(self.parent), str(self.version)])
    
    def __repr__(self):
        return "-".join([str(self.data), str(self.parent), str(self.version)])

    def update_data(self, newdata):
        self.data = newdata

class UnionFind:
    """ UnionFind operates on Nodes from the Node class"""
    def __init__(self):
        self.nodelist = []

    def makeset(self, x):
        newnode = Node(x, None, 0)
        self.nodelist.append(newnode)
        return newnode
        
    def find(self, x):
        if x.parent != None:
            x.parent = self.find(x.parent)
        return x.parent
            
    def union(self, x, y):
        xroot = self.find(x)
        yroot = self.find(y)

        if xroot == yroot:
            return
        
        if xRoot.rank < yRoot.rank:
            xRoot.parent = yRoot
        elif xRoot.rank > yRoot.rank:
            yRoot.parent = xRoot
        else:
            yRoot.parent = xRoot
            xRoot.rank = xRoot.rank + 1

def construct_forest_parent_dict(vertex_dict, forest_dict):
    out = {}
    for key in vertex_dict:
        if vertex_dict[key][1].parent != None:
            out[key] = vertex_dict[key][1].parent.data
    for key in forest_dict:
        node = forest_dict[key]
        if node.parent != None:
            out[node.data] = node.parent.data
    return out

class DynamicSCC:
    def __init__(self):
        self._forest_index = 0
        self.ufind = UnionFind()
        ### vertices are maps from data to unionfind node, lca forestnode
        self.vertices = {}
        ### forest vertices are nodes used solely by the LCA structure
        self.forest_vertices = {}
        ## a map from forest vertices to children, so that we can
        ## easily reconstruct the SCCs
        self.children = {}
        self._dynamic_edges = []
        self._t = 0
        self._dynamic_edges += [set([]), set([])]
        self.G = nx.DiGraph()

    def current_version(self):
        return self._t

    def insert_vertices(self, vertices):
        for v in vertices:
            self.vertices[v] = (Node(v, None), Node(v, None))
            
    def _scc(self, vertices, edges):
        G = nx.DiGraph()
        G.add_nodes_from(vertices)
        G.add_edges_from(edges)
        return nx.strongly_connected_components(G)

    def _findSCC(self, edges, t):
        """ When adding or deleting a set of edges, determine
        the new SCCs in the resulting graph"""
        edgeset = set([])
        vertexset = set([])
        for edge in edges:
            u = edge[0]
            v = edge[1]
            vertexset.add(u)
            vertexset.add(v)
            addu = self.ufind.find(self.vertices[u][0])
            addv = self.ufind.find(self.vertices[v][0])
            if addu == None:
                addu = u
            else:
                addu = addu.data
            if addv == None:
                addv = v
            else:
                addv = addv.data
            edgeset.add((addu, addv))
        sccs = self._scc(vertexset, edgeset)
        ## zero the set of children, and rebuild from scratch
        self.children = {}
        
        for component in sccs:
            if len(component) > 1:
                self._forest_index += 1
                c = Node("".join(["forest", str(self._forest_index)]), None)
                c.version = t
                self.forest_vertices[c.data] = c
                self.children[c] = []
                for j in range(len(component)):
                    a = self.vertices[component[0]]
                    b = self.vertices[component[j]]
                    if j > 0:
                        self.ufind.union(a[0], b[0])
                    b[1].parent = c
                    self.children[c].append(b[1])
    ## end _findScc

    def _shift(self, edges1, edges2):
        to_remove = set([])
        for edge in edges1:
            u = self.ufind.find(self.vertices[edge[0]][0])
            v = self.ufind.find(self.vertices[edge[1]][0])
            if u != v or u == None or v == None:
                to_remove.update([edge])
        
        edges1 -= to_remove
        edges2 |= to_remove
    ## end _shift
        
    def insert_edges(self, edges):
        """ Given a set of edges, add them to the graph. """
        ## first, find the vertices corresponding to the edges
        new_edges = set([])
        self._t += 1
        self._dynamic_edges.append(set([]))
        self._dynamic_edges[self._t] |= edges
        self._findSCC(self._dynamic_edges[self._t], self._t)
        self._shift(self._dynamic_edges[self._t], self._dynamic_edges[self._t+1])
    ## end insert

    def delete(self, edges):
        for v in self.vertices:
            self.vertices[v][1].parent = None
        for i in range(self._t):
            self._dynamic_edges[i] -= edges
            self._findSCC(self._dynamic_edges[i], i)
            self._shift(self._dynamic_edges[i], self._dynamic_edges[i+1])
        self._dynamic_edges[self._t + 1] -= edges
        

    def delete_vertex(self, vertex):
        """ Delete all edges incident to a vertex """
        deleted = set([])
        for s in self._dynamic_edges:
            for edge in s:
                if vertex in edge and edge not in deleted:
                    deleted |= set([edge])
        self.delete(deleted)
        del self.vertices[vertex]
        
    def query(self, u, v, t = None):
        """ Are nodes u and v in the same SCC in version t?"""
        if t is None: # by default, use latest generation
            t = self._t
        nodeu = self.vertices[u]
        nodev = self.vertices[v]
        if nodeu[1].parent == nodeu or nodev[1].parent == v:
            return False
        else:
            parent = construct_forest_parent_dict(self.vertices, self.forest_vertices)
            if u not in parent or v not in parent:
                return False
            tree = LCA.LCA(parent)
            return self.forest_vertices[tree(u,v)[0]].version <= t
    ## end query

    def getSCC(self, u, i = None):
        """ Get the scc containing u at version i"""
        if i is None: # by default, use latest generation
            i = self._t
        tmp = self.vertices[u][1].parent
        if tmp == None:
            return [u]
        ## First search up for the latest parent
        prev = u
        while tmp.version <= i:
            prev = tmp
            if tmp.parent == None:
                break
            else:
                tmp = tmp.parent
        tmp = prev
        ## Now, do a BFS for all the leaves
        if tmp not in self.children:
            return [u]
        visited = list(self.children[tmp])
        leaves = []
        while len(visited) >= 1:
            v = visited.pop(0)
            if v not in self.children:
                leaves.append(v)
            else:
                visited.extend(list(self.children(v)))
        return [v.data for v in leaves]
    ## end getSCC

if __name__ == '__main__':
    test = DynamicSCC()
    test.insert_vertices(range(6))
    print test.query(0,1)
    test.insert_edges(set([(0,1), (2,0)]))
    print test.query(0,1)
    print test.getSCC(0)
    test.insert_edges(set([(1,2)]))
    print test.query(0,1)
    print test.getSCC(0)
    test.delete(set([(1,2)]))
    print test.query(0,1)
    print test.getSCC(1)
    test.insert_edges(set([(1,2)]))
    print test.query(0,1)
    print test.getSCC(0)
    test.delete(set([(1,2)]))
    print test.query(0,1)
    print test.getSCC(1)
    test.insert_edges(set([(1,2)]))
    print test.query(0,1)
    print test.getSCC(0)
    test.delete_vertex(0)
    print test.getSCC(2)
    print test._dynamic_edges
    
