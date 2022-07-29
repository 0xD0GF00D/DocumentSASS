import collections
import re
import sys
from collections import *

# We used delimiters like the one below to separate different outputs.
example = "<0x0 0x0 0>"
# The first value is the destination pointer, the second the src, and the third the size in bytes.
delimiter = "<0x[\da-f]+ 0x[\da-f]+ [\d]+>"

pattern = re.compile(delimiter)
assert pattern.match(example)

def getstring(data, src, firstline=False, unique=False):
    # Put unique = true to remove duplicate lines from string. Mor or may not work.
    collect = False
    partial = []
    full = collections.OrderedDict() if unique else []
    for line in data.splitlines() + [example]: # <- we add an empty token to push out last line.
        if pattern.match(line):  # Start of a string.
            collect = line.split()[1] == src  # The code matches. Start collecting pieces of the string.
            if unique:
                full['\n'.join(partial)] = None
            else:
                full.append('\n'.join(partial))
            partial.clear()
        elif collect:
            if firstline:
                return line
            partial.append(line)


    # Collect the partial results. And connect them not by newlines.
    return ''.join(full)


def getkey(entry):
    # Unpack "<a b c>" into a,b,c
    return entry[1:-1].split()

def getfile(data, name):
    # Find the occurence of string starting with name, and extract key.
    match = re.search(delimiter + '\n' + name, data).group()
    _, src, _ = getkey(match.splitlines()[0])
    # t = True
    #for match in re.findall(delimiter + '\n' + name, data):
    #    _, src, _ = getkey(match.splitlines()[0])
        # print(src)
        # 0x449e908
        # 0x449a840
        # Then use the key to get the rest of the string.
    return getstring(data, src)

def getcounts(data):
    # The basic idea is that a string-buffer will end up having written the whole file.
    # Therefore we can look through the amount of trafic to find the strings of interest.
    keys = map(getkey, pattern.findall(data))
    counts = defaultdict(int)
    for dst, src, size in keys:
        size = int(size)
        # We only really care for the src, as this is the buffer containing the string.
        counts[src] = counts[src] + size
    return counts

def getreferences(data):
    keys = map(getkey, pattern.findall(data))
    # Something is written a..........b, where a, b is the start and end address.
    # Then something is written: b.......c
    # We would now like to trace this connection a->c starting in c. So the value should be the parent.
    points = {int(entry[0][2:], 16)+int(entry[2]): int(entry[0][2:], 16) for entry in keys}
    points_rev = {int(entry[0][2:], 16):int(entry[0][2:], 16)+int(entry[2]) for entry in keys}

    # Now, toplevels are those with no parents, e.g. a.
    toplevels = [value for value in points.values() if value not in points]
    bottomlevels = [value for value in points_rev.values() if value not in points_rev]


    # Now we can remove all of those
    print(len(bottomlevels))
    #print(len(points))

    return points

def remsuffix(inpt, suffix):
    # https://stackoverflow.com/a/1038845
    if inpt.endswith(suffix):
        inpt = inpt[:-len(suffix)]
    return inpt

if __name__ == "__main__":
    if len(sys.argv) == 1:
        raise Exception('No input file name given.')

    for fname in sys.argv[1:]:
        with open(fname, "r", encoding="ascii") as f:
            data = f.read()

        fname = remsuffix(remsuffix(fname, '.txt'), '_intercept')
        instructions = getfile(data, 'ARCHITECTURE')[:-2]
        with open(fname + '_instructions.txt', "w") as f:
            f.write(instructions)

        latencies = getfile(data, 'OPERATION SETS')
        with open(fname + '_latencies.txt', "w") as f:
            f.write(latencies)

    if False:
        threshold = 0  # Threshold at 5 Kb e.g.
        goodones = sorted((x[1], x[0]) for x in getcounts(data).items() if x[1] >= threshold)
        for size, src in reversed(goodones):
            try:
                firstline = getstring(data, src, firstline=True)
                txt = getfile(data, firstline)
                print(size, len(txt), src, firstline)
            except e:
                pass


        # print(map(lambda x: getstring(x[1]), goodones))
