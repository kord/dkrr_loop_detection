
import math, sys
from collections import Counter
import numbers


class StatsBuddy(object):
    ''' Track statistics for input numbers '''
    def __init__(self, data=None):
        self.size = 0
        self.total = 0
        self.mean = 0
        self._M2 = 0 # sum of squares of differences from the (current) mean
        self._M4 = 0
        self._M3 = 0
        
        self.min = sys.maxint
        self.max = -(sys.maxint +1) # magic number is minint, as if python doesn't have unlimited precision integers
        self.sum_of_squares = 0
        if data is not None:
            self.add(data)


    def add(self, data):
        ''' Add a new number or list of numbers to this StatsBuddy'''
        if isinstance(data, numbers.Number):
            self.size += 1
            self.total += data
            
            if data < self.min: self.min = data
            if data > self.max: self.max = data

            self.sum_of_squares += data**2

            # see http://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
            # this is nice and stable
            delta = data - self.mean
            self.mean = self.mean + 1.0 * delta / self.size
            self._M2 = self._M2 + delta * (data - self.mean)

            '''
            delta_n = delta / self.size
            delta_n2 = delta_n**2
            term1 = delta * delta_n * (self.size - 1)
            mean = self.mean + delta_n
            self._M4 = self._M4 + term1 * delta_n2 * (self.size**2 - 3 * self.size + 3) + 6 * delta_n2 * self._M2 - 4 * delta_n * self._M3
            self._M3 = self._M3 + term1 * delta_n * (self.size - 2) - 3 * delta_n * self._M2
            self._M2 = self._M2 + term1
            '''
        else:
            for d in data: self.add(d)

 

    #kurtosis = property(lambda self: (self.size * self._M4) / (self._M2**2) - 3)
    variance = property(lambda self: 1.0 * self._M2 / (self.size - 1))
    stdev = property(lambda self: math.sqrt(self.variance))


    __len__ = lambda self: self.size
    def __str__(self):
        if self.size == 0:
            return '<StatsBuddy: Untouched>'
        return '<StatsBuddy: Size: {}, Mean: {:.5g}, Stdev: {:.5g}>'.format(self.size, self.mean, self.stdev)

    def __add__(self, oth):
        ret = StatsBuddy()
        ret.total = 1.0 * self.total + oth.total
        ret.size = self.size + oth.size
        ret.mean = ret.total / ret.size if ret.size > 0 else 0
        ret.min = min(self.min, oth.min)
        ret.max = max(self.max, oth.max)
        ret.sum_of_squares = self.sum_of_squares + oth.sum_of_squares

        # correcting the tracked data is a little bit tricky for this stable variable
        # i'm not quite sure that this technique is also stable.
        ret._M2 = self._M2 + oth._M2
        # correction terms
        ret._M2 += self.size * (ret.mean**2 - self.mean**2) + 2.0 * self.total * (self.mean - ret.mean)
        ret._M2 += oth.size * (ret.mean**2 - oth.mean**2) + 2.0 * oth.total * (oth.mean - ret.mean)
        return ret




class Buckets(object):
    def __init__(self, min, max, numbuckets=40):
        self.numbuckets = numbuckets
        self.bucketsize = 1.0 * (max - min) / self.numbuckets
        self.bucketmin = min
        self.bucketmax = max
        self.size = 0
        self.buckets = [0] * numbuckets
        self.too_small = 0
        self.too_big = 0

    def add(self, data):
        if isinstance(data, numbers.Number): 
            self.size += 1
            bnum = int(math.floor(1.0 * (data - self.bucketmin) / self.bucketsize))
            if bnum < 0:
                self.too_small += 1
            elif bnum >= self.numbuckets:
                self. too_big += 1
            else:
                self.buckets[bnum] += 1
        else:
            # assume the input generates values to input
            for d in data:
                self.add(d)

    __len__ = lambda self: self.size

    def graph(self, numsize=14, max_width=65):
        '''
        Get a handy string that providesa plot-like visual representation of the vucket sizes
        '''
        ret = ['<Bucket> object with {} items\n'.format(len(self))]
        fullestsize = max([self.buckets[bnum] for bnum in range(self.numbuckets)])
        for s, l, count in self.iter_buckets():
            ret.append('[{:.3g},{:.3g}]'.format(s, l).ljust(numsize))
            if count == 0: 
                ret.append('empty')
            else:
                width = int(math.floor(1.0 * max_width * count / fullestsize))
                ret.append('-' * width)
            ret.append('\n')
        return ''.join(ret)

    def iter_buckets(self):
        small = self.bucketmin
        yield (-sys.maxint- 1, self.bucketmin, self.too_small)
        for bnum in range(self.numbuckets):
            yield (small, small + self.bucketsize, self.buckets[bnum])
            small += self.bucketsize
        yield (self.bucketmax, sys.maxint, self.too_big)
            

    def __str__(self):
        ret = ['<Buckets: Size {}, '.format(len(self))]
        for min, max, count in self.iter_buckets():
            s = '[{:g},{:g}]: {}'.format(min, max, count)
            ret.append(s)
            ret.append(', ')
        del ret[-1] # drop the last comma

        ret.append('>')
        return ''.join(ret)




if __name__ == '__main__':
    from random import Random
    rand = Random()

    b = Buckets(0,6, 50)
    for r in xrange(50000):
        b.add(rand.gammavariate(2,1))
    print b
    print b.graph()

    s = StatsBuddy(range(4))
    t = StatsBuddy(range(4,77))
    u = StatsBuddy(range(77))

    print u, len(u)
    print s+t

