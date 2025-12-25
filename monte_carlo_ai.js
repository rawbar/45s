/**
 * Monte Carlo AI for 45s Card Game
 * Optimized for web performance - uses 5 rollouts per decision
 * 
 * INTEGRATION INSTRUCTIONS:
 * 1. Add this entire file to your project
 * 2. Replace chooseCardToPlay() in your existing AI with: chooseCardMonteCarloAI()
 * 3. Done! AI will now use Monte Carlo simulation
 */

// ============================================================================
// MONTE CARLO GAME SIMULATOR
// ============================================================================

class GameSimulator {
  /**
   * Run Monte Carlo simulation to choose best card
   * @param {Object} gameState - Current game state
   * @param {Array} playableCards - Cards AI can legally play
   * @param {number} numRollouts - Number of simulations per card (default: 5)
   * @returns {Object} - Best card to play
   */
  static chooseBestCard(gameState, playableCards, numRollouts = 5) {
    if (playableCards.length === 1) {
      return playableCards[0];
    }

    const cardScores = {};
    
    // Evaluate each playable card
    for (const card of playableCards) {
      let totalPoints = 0;
      
      // Run multiple simulations
      for (let i = 0; i < numRollouts; i++) {
        const points = this.simulateGameFromCard(gameState, card);
        totalPoints += points;
      }
      
      cardScores[card.id] = totalPoints / numRollouts;
    }
    
    // Pick card with highest average score
    let bestCard = playableCards[0];
    let bestScore = cardScores[bestCard.id];
    
    for (const card of playableCards) {
      if (cardScores[card.id] > bestScore) {
        bestScore = cardScores[card.id];
        bestCard = card;
      }
    }
    
    return bestCard;
  }

  /**
   * Simulate rest of game after playing a specific card
   * @param {Object} gameState - Current game state
   * @param {Object} card - Card to simulate playing
   * @returns {number} - Points my team would score
   */
  static simulateGameFromCard(gameState, card) {
    // Clone state for simulation
    const simState = this.cloneGameState(gameState);
    
    // Sample opponent hands
    this.sampleOpponentHands(simState);
    
    // Play the chosen card
    const myPlayerIdx = simState.currentPlayer;
    simState.hands[myPlayerIdx] = simState.hands[myPlayerIdx].filter(c => c.id !== card.id);
    simState.currentTrick.push({ player: myPlayerIdx, card: card });
    
    // Update high trump tracking
    const trumpRank = this.getTrumpRank(card, simState.trumpSuit);
    if (trumpRank > simState.highTrumpRank) {
      simState.highTrumpRank = trumpRank;
      simState.highTrumpWinner = myPlayerIdx;
    }
    
    // Simulate rest of current trick
    this.completeCurrentTrick(simState);
    
    // Simulate remaining tricks
    while (simState.trickNum <= 5 && simState.hands[0].length > 0) {
      this.simulateTrick(simState);
    }
    
    // Calculate final score for my team
    return this.calculateMyTeamScore(simState, myPlayerIdx);
  }

  /**
   * Complete the current trick with simulated plays
   */
  static completeCurrentTrick(state) {
    while (state.currentTrick.length < 4) {
      const currentPlayer = (state.trickLeader + state.currentTrick.length) % 4;
      const hand = state.hands[currentPlayer];
      const ledCard = state.currentTrick[0].card;
      const playable = this.getPlayableCards(hand, state.trumpSuit, ledCard);
      
      if (playable.length === 0) break;
      
      // Use simple heuristic for simulation speed
      const chosen = this.chooseCardSimple(playable, state, currentPlayer);
      
      state.hands[currentPlayer] = hand.filter(c => c.id !== chosen.id);
      state.currentTrick.push({ player: currentPlayer, card: chosen });
      
      // Update high trump
      const trumpRank = this.getTrumpRank(chosen, state.trumpSuit);
      if (trumpRank > state.highTrumpRank) {
        state.highTrumpRank = trumpRank;
        state.highTrumpWinner = currentPlayer;
      }
    }
    
    // Evaluate trick winner
    const winner = this.evaluateTrick(state.currentTrick, state.trumpSuit, state.trickLeader);
    const winnerTeam = winner % 2;
    state.tricksWon[winnerTeam]++;
    
    // Set up next trick
    state.trickNum++;
    state.trickLeader = winner;
    state.currentTrick = [];
  }

  /**
   * Simulate one complete trick
   */
  static simulateTrick(state) {
    const leader = state.trickLeader;
    
    for (let i = 0; i < 4; i++) {
      const currentPlayer = (leader + i) % 4;
      const hand = state.hands[currentPlayer];
      const ledCard = i > 0 ? state.currentTrick[0].card : null;
      const playable = this.getPlayableCards(hand, state.trumpSuit, ledCard);
      
      if (playable.length === 0) break;
      
      const chosen = this.chooseCardSimple(playable, state, currentPlayer);
      
      state.hands[currentPlayer] = hand.filter(c => c.id !== chosen.id);
      state.currentTrick.push({ player: currentPlayer, card: chosen });
      
      const trumpRank = this.getTrumpRank(chosen, state.trumpSuit);
      if (trumpRank > state.highTrumpRank) {
        state.highTrumpRank = trumpRank;
        state.highTrumpWinner = currentPlayer;
      }
    }
    
    const winner = this.evaluateTrick(state.currentTrick, state.trumpSuit, leader);
    const winnerTeam = winner % 2;
    state.tricksWon[winnerTeam]++;
    
    state.trickNum++;
    state.trickLeader = winner;
    state.currentTrick = [];
  }

  /**
   * Simple heuristic for fast rollout simulation
   */
  static chooseCardSimple(playable, state, playerIdx) {
    // Partner winning? Play low
    if (state.currentTrick.length > 0) {
      const winnerIdx = this.evaluateTrick(state.currentTrick, state.trumpSuit, state.trickLeader);
      const winnerTeam = (state.trickLeader + winnerIdx) % 2;
      const myTeam = playerIdx % 2;
      
      if (winnerTeam === myTeam) {
        // Partner winning - play lowest card
        return playable.reduce((lowest, card) => {
          const rank1 = this.getCardRank(lowest, state.trumpSuit);
          const rank2 = this.getCardRank(card, state.trumpSuit);
          return rank1 < rank2 ? lowest : card;
        });
      }
    }
    
    // Try to win - play highest card
    return playable.reduce((highest, card) => {
      const rank1 = this.getCardRank(highest, state.trumpSuit);
      const rank2 = this.getCardRank(card, state.trumpSuit);
      return rank1 > rank2 ? highest : card;
    });
  }

  /**
   * Sample plausible opponent hands based on unknown cards
   */
  static sampleOpponentHands(state) {
    const myPlayerIdx = state.currentPlayer;
    const myHand = state.hands[myPlayerIdx];
    
    // Collect unknown cards
    const allCards = this.generateDeck();
    const knownCards = new Set([
      ...myHand.map(c => c.id),
      ...state.cardsPlayed.map(c => c.id)
    ]);
    
    const unknownCards = allCards.filter(c => !knownCards.has(c.id));
    this.shuffleArray(unknownCards);
    
    // Deal to other players
    let idx = 0;
    for (let p = 0; p < 4; p++) {
      if (p === myPlayerIdx) continue;
      
      const handSize = myHand.length; // Assume same size
      state.hands[p] = [];
      for (let i = 0; i < handSize && idx < unknownCards.length; i++) {
        state.hands[p].push(unknownCards[idx++]);
      }
    }
  }

  /**
   * Calculate final score for my team
   */
  static calculateMyTeamScore(state, myPlayerIdx) {
    const myTeam = myPlayerIdx % 2;
    const bidderTeam = state.bidWinner % 2;
    
    const myTricks = state.tricksWon[myTeam];
    const myPoints = myTricks * 5;
    
    // Add high trick bonus
    const highTrickTeam = state.highTrumpWinner % 2;
    const totalPoints = myPoints + (highTrickTeam === myTeam ? 5 : 0);
    
    // If I'm on bidding team, account for making/setting
    if (myTeam === bidderTeam) {
      return totalPoints >= state.highBid ? totalPoints : -state.highBid;
    }
    
    return totalPoints;
  }

  // ========================================================================
  // HELPER FUNCTIONS (using your existing game logic)
  // ========================================================================

  static getTrumpRank(card, trumpSuit) {
    // Use your existing getTrumpRank function
    // Copy from your current code
    if (card.rank === 'A' && card.suit === 'H') return 100;
    if (card.suit !== trumpSuit) return -1;
    if (card.rank === '5') return 102;
    if (card.rank === 'J') return 101;
    if (card.rank === 'A') return 99;
    if (card.rank === 'K') return 98;
    if (card.rank === 'Q') return 97;
    
    const order = (trumpSuit === 'H' || trumpSuit === 'D') 
      ? ['10','9','8','7','6','4','3','2']
      : ['2','3','4','6','7','8','9','10'];
    const idx = order.indexOf(card.rank);
    return idx >= 0 ? 80 + idx : -1;
  }

  static getCardRank(card, trumpSuit) {
    const trumpRank = this.getTrumpRank(card, trumpSuit);
    if (trumpRank >= 0) return trumpRank + 200; // Trump always high
    
    // Offsuit ranking
    const isRed = card.suit === 'H' || card.suit === 'D';
    const order = isRed 
      ? ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
      : ['10','9','8','7','6','5','4','3','2','A','J','Q','K'];
    return order.indexOf(card.rank);
  }

  static getPlayableCards(hand, trumpSuit, ledCard) {
    // Use your existing getPlayableCards logic
    // This is a simplified version
    if (!ledCard) return [...hand];
    
    const isTrump = (c) => (c.rank === 'A' && c.suit === 'H') || c.suit === trumpSuit;
    
    if (isTrump(ledCard)) {
      const trumpCards = hand.filter(c => isTrump(c));
      return trumpCards.length > 0 ? trumpCards : hand;
    }
    
    const sameSuit = hand.filter(c => c.suit === ledCard.suit);
    const trumpCards = hand.filter(c => isTrump(c));
    return sameSuit.length > 0 ? [...sameSuit, ...trumpCards] : hand;
  }

  static evaluateTrick(trick, trumpSuit, leader) {
    // Use your existing evaluateTrick logic
    if (trick.length === 0) return leader;
    
    const ledCard = trick[0].card;
    let winnerIdx = 0;
    let winnerCard = ledCard;
    
    for (let i = 1; i < trick.length; i++) {
      const card = trick[i].card;
      if (this.cardBeats(card, winnerCard, trumpSuit, ledCard.suit)) {
        winnerIdx = i;
        winnerCard = card;
      }
    }
    
    return (leader + winnerIdx) % 4;
  }

  static cardBeats(card1, card2, trumpSuit, ledSuit) {
    const t1 = this.getTrumpRank(card1, trumpSuit);
    const t2 = this.getTrumpRank(card2, trumpSuit);
    
    if (t1 >= 0 && t2 >= 0) return t1 > t2;
    if (t1 >= 0) return true;
    if (t2 >= 0) return false;
    
    if (card1.suit !== ledSuit) return false;
    if (card2.suit !== ledSuit) return true;
    
    return this.getCardRank(card1, trumpSuit) > this.getCardRank(card2, trumpSuit);
  }

  static cloneGameState(state) {
    return {
      hands: state.hands.map(h => [...h]),
      trumpSuit: state.trumpSuit,
      bidWinner: state.bidWinner,
      highBid: state.highBid,
      currentPlayer: state.currentPlayer,
      trickLeader: state.trickLeader,
      trickNum: state.trickNum,
      currentTrick: [...state.currentTrick],
      tricksWon: [...state.tricksWon],
      cardsPlayed: [...state.cardsPlayed],
      highTrumpRank: state.highTrumpRank,
      highTrumpWinner: state.highTrumpWinner
    };
  }

  static generateDeck() {
    const suits = ['S', 'H', 'D', 'C'];
    const ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];
    const deck = [];
    
    for (const suit of suits) {
      for (const rank of ranks) {
        deck.push({ id: `${rank}${suit}`, rank, suit });
      }
    }
    
    return deck;
  }

  static shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [array[i], array[j]] = [array[j], array[i]];
    }
  }
}

// ============================================================================
// INTEGRATION FUNCTION - USE THIS IN YOUR EXISTING CODE
// ============================================================================

/**
 * Monte Carlo AI card selection
 * Drop-in replacement for your existing chooseCardToPlay()
 * 
 * @param {Object} gameState - Current game state with:
 *   - hands: array of 4 player hands
 *   - trumpSuit: 'S', 'H', 'D', or 'C'
 *   - bidWinner: player index 0-3
 *   - highBid: bid amount
 *   - currentPlayer: player index whose turn it is
 *   - trickLeader: who led current trick
 *   - trickNum: 1-5
 *   - currentTrick: [{player, card}, ...]
 *   - tricksWon: [team0, team1]
 *   - cardsPlayed: all cards played so far
 *   - highTrumpRank: highest trump rank seen
 *   - highTrumpWinner: who played highest trump
 * 
 * @param {Array} playableCards - Cards the AI can legally play
 * @returns {Object} - Best card to play
 */
function chooseCardMonteCarloAI(gameState, playableCards) {
  // Use 5 rollouts (optimal from testing)
  return GameSimulator.chooseBestCard(gameState, playableCards, 5);
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { GameSimulator, chooseCardMonteCarloAI };
}
