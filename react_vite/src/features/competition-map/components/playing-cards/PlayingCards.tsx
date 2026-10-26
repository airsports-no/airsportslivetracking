import React from 'react';
import Hand from './Hand';

interface PlayingCardsProps {
    playingCards: { 
        card?: string; 
        rank?: string; 
        suit?: string;
        card_string?: string;
        card_value?: string;
        card_suit?: string;
    }[];
    /** The size of a card in pixels: smaller where the hand sits in a slim row. */
    cardSize?: number;
    layout?: 'fan' | 'arc';
}

const PlayingCards: React.FC<PlayingCardsProps> = ({ playingCards, cardSize = 120, layout = 'fan' }) => {
    if (!playingCards) return null;
    const cards = playingCards
        .map((card) => {
            // Priority 1: Direct card string (initial load or rest api)
            if (card?.card) return card.card.toLowerCase();
            // Priority 2: card_string (websocket)
            if (card?.card_string) return card.card_string.toLowerCase();
            // Priority 3: Combined rank/suit (initial load object)
            if (card?.rank && card?.suit) return (card.rank + card.suit).toLowerCase();
            // Priority 4: Combined value/suit (websocket object)
            if (card?.card_value && card?.card_suit) return (card.card_value + card.card_suit).toLowerCase();
            
            return null;
        })
        .filter((card): card is string => !!card);
    
    if (cards.length === 0) return null;
    
    return (
        <Hand
            hide={false}
            layout={layout}
            cards={cards}
            cardSize={cardSize}
        />
    );
};

export default PlayingCards;
