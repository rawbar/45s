"""
audit_lowest_trump.py -- does the champion AI ALWAYS follow a trump lead with its
LOWEST trump when it cannot beat the card currently winning the trick?

If yes, "everything I still hold ranks above the card I just played" is a sound
deduction vs AI opponents.  Any exception printed here is either an AI bug or a
hole in the deduction.

  python -m bidding_simulator_v2.audit_lowest_trump --deals 20000 --seed 1
"""
import sys, os, io, random, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and (sys.stdout.encoding or '').lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from game_engine import Card, Suit, get_trump_rank, get_playable_cards, evaluate_trick
from bidding_simulator_v2.improved_ai import ImprovedAI, _is_trump
from bidding_simulator_v2.round_runner import play_round

RANKS = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
STATS = collections.Counter()
EXC = []

class AuditAI(ImprovedAI):
    def choose_card(self, state, play_history):
        card = super().choose_card(state, play_history)
        trump = state.trump_suit
        trick = state.current_trick
        hand = state.hands[self.player_idx]
        if trick and get_trump_rank(trick[0][1], trump) >= 0:            # trump led, I'm following
            led = trick[0][1]
            legal = get_playable_cards(hand, trump, led)
            if card not in legal: return card
            my_trumps = [c for c in hand if get_trump_rank(c, trump) >= 0]
            if not my_trumps: return card
            cur_best = max(get_trump_rank(c, trump) for _, c in trick if get_trump_rank(c, trump) >= 0)
            can_beat = any(get_trump_rank(c, trump) > cur_best for c in my_trumps)
            played_trump = get_trump_rank(card, trump) >= 0
            lowest = min(get_trump_rank(c, trump) for c in my_trumps)
            tag = 'canbeat' if can_beat else 'cannotbeat'
            # partner currently winning?
            win_seat = evaluate_trick(list(trick) + [(self.player_idx, card)], trump, state.trick_leader) if len(trick) == 3 else None
            if played_trump:
                beats = get_trump_rank(card, trump) > cur_best
                STATS[('winning_play' if beats else 'LOSING_play') + ':' + tag] += 1
                if (not beats) and get_trump_rank(card, trump) != lowest:
                    STATS['LOSING_play_NOT_lowest:' + tag] += 1
                    if len(EXC) < 4000:
                        EXC.append(('LOSE-NOT-LOWEST-' + tag, state.trick_num, self.player_idx, [str(c.rank)+c.suit.value for c in hand],
                                    [(p, str(c.rank)+c.suit.value) for p, c in trick], str(card.rank)+card.suit.value,
                                    state.bid_winner, state.high_bid, trump.value))
                STATS[tag + ':played_trump'] += 1
                if get_trump_rank(card, trump) != lowest:
                    STATS[tag + ':NOT_lowest'] += 1
                    if len(EXC) < 4000:
                        EXC.append((tag, state.trick_num, self.player_idx, [str(c.rank)+c.suit.value for c in hand],
                                    [(p, str(c.rank)+c.suit.value) for p, c in trick], str(card.rank)+card.suit.value,
                                    state.bid_winner, state.high_bid, trump.value))
            else:
                STATS[tag + ':played_offsuit(renege)'] += 1
                if not can_beat and lowest < 100 and len(my_trumps) >= 1:
                    # reneged while holding a non-top-3 trump? illegal, but count anyway
                    STATS[tag + ':renege_holding_low'] += 1
        return card

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--deals', type=int, default=5000); ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args(); rng = random.Random(a.seed)
    proto = [Card(r, s) for s in Suit for r in RANKS]
    for _ in range(a.deals):
        deck = proto[:]; rng.shuffle(deck)
        trump = rng.choice(list(Suit)); bid = rng.choice([15, 20, 20, 25, 30])
        hands = [deck[i*5:(i+1)*5] for i in range(4)]; kitty = deck[20:23]; rest = deck[23:]
        ais = [AuditAI(i) for i in range(4)]
        play_round(bid, trump, hands, kitty, rest, ais)
    for k in sorted(STATS): print(f'{k:45s} {STATS[k]}')
    print('\nfirst exceptions (cannot-beat, played non-lowest trump):')
    n = 0
    for e in EXC:
        if e[0].startswith('LOSE-NOT-LOWEST'):
            print(' ', e); n += 1
            if n >= 12: break
    c = collections.Counter(e[5] for e in EXC if e[0]=='cannotbeat')
if __name__ == '__main__': main()
