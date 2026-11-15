"""How often does pbs-floor change the champion's card?  python -m bidding_simulator_v2.diverge_pbs --deals 5000"""
import sys, os, io, random, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer'): sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from game_engine import Card, Suit
from bidding_simulator_v2.improved_ai import ImprovedAI
from bidding_simulator_v2.round_runner import play_round
RANKS=['2','3','4','5','6','7','8','9','10','J','Q','K','A']
N=collections.Counter(); EX=[]
class Probe(ImprovedAI):
    def choose_card(self, state, hist):
        c = super().choose_card(state, hist)
        alt = ImprovedAI(self.player_idx, {'pbs_floor': True}).choose_card(state, hist)
        N['decisions'] += 1
        if alt is not c and (alt.rank, alt.suit) != (c.rank, c.suit):
            N['diverged'] += 1
            if len(EX) < 6: EX.append((state.trick_num, self.player_idx, [x.rank+x.suit.value for x in state.hands[self.player_idx]], c.rank+c.suit.value, alt.rank+alt.suit.value, state.trump_suit.value, state.bid_winner))
        return c
ap=argparse.ArgumentParser(); ap.add_argument('--deals',type=int,default=3000); a=ap.parse_args(); rng=random.Random(7)
proto=[Card(r,s) for s in Suit for r in RANKS]
for _ in range(a.deals):
    d=proto[:]; rng.shuffle(d); t=rng.choice(list(Suit)); bid=rng.choice([15,20,20,25,30])
    play_round(bid,t,[d[i*5:(i+1)*5] for i in range(4)],d[20:23],d[23:],[Probe(i) for i in range(4)])
print(dict(N)); [print(e) for e in EX]
