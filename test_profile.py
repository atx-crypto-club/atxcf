import cProfile
import StringIO
import pstats

pr = cProfile.Profile()
pr.enable()

import atxcf

pr.disable()
s = StringIO.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats()
print s.getvalue()

