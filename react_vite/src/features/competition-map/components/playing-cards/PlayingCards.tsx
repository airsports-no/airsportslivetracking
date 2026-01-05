import React from 'react';
import Hand from './Hand';

interface PlayingCardsProps {
    playingCards: { card: string }[];
}

const PlayingCards: React.FC<PlayingCardsProps> = ({ playingCards }) => {
    const cards = playingCards.map((card) => card.card.toLowerCase());
    
    return (
        <Hand
            hide={false}
            layout={"fan"}
            cards={cards}
            cardSize={120} // Re-increased size
        />
    );
};

export default PlayingCards;
