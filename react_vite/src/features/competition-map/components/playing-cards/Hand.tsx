import React, { useState, useEffect, useMemo } from 'react';
import './Hand.css';
import PlayingCard from './PlayingCard';

interface HandProps {
    cards: string[];
    cardSize?: number;
    elevated?: string;
    layout?: 'fan' | 'spread' | 'stack';
    hide?: boolean;
    onClick?: (card: string) => void;
}

const Hand: React.FC<HandProps> = (props) => {
    const {
        cards: initialCards,
        cardSize = 250,
        layout = 'fan',
        hide = false,
        onClick = () => {},
    } = props;

    const [cards, setCards] = useState(initialCards);

    useEffect(() => {
        setCards(initialCards);
    }, [initialCards]);

    const handLength = cards.length;

    const getStyle = useMemo(() => {
        if (layout === 'fan') {
            const curl = Math.pow(handLength, 1.30) * 10;
            const deg = handLength > 1 ? -handLength * 15 : 0;
            const initialDown = handLength * 7;
            const initialOver = curl;
            
            return (num: number) => {
                const degs = (deg / 2) - (deg / (handLength - 1)) * num;
                const down = (initialDown / 2) - (initialDown / (handLength - 1)) * num;
                const over = (initialOver / 2) - (initialOver / (handLength - 1)) * num;
                const overHalf = num > (handLength - 1) / 2;
                
                return {
                    zIndex: num,
                    transform: `translateY(${(overHalf ? -down : down)}%) translateX(${(-50 + over * -1)}%) rotate(${degs}deg)`
                };
            };
        } else if (layout === 'spread') {
            const initialOver = 110 * (handLength - 1);
            return (num: number) => {
                const over = (initialOver / 2) - (initialOver / (handLength - 1)) * num;
                return {
                    zIndex: num,
                    transform: `translateX(${(-50 + over * -1)}%)`
                };
            };
        } else { // stack
            return (num: number) => {
                const over = 50 - (20 / handLength) * num;
                return {
                    zIndex: num,
                    transform: `translateX(${(-over)}%)`
                };
            };
        }
    }, [layout, handLength]);

    return (
                <div className={'Hand'} style={{ height: cardSize }} >
            {cards.map((card, index) => (
                <PlayingCard
                    key={card}
                    height={cardSize}
                    card={card}
                    style={{ ...getStyle(index), height: `${cardSize}px` }}
                    flipped={hide}
                    onClick={onClick}
                    zIndex={index}
                />
            ))}
        </div>
    );
};

export default Hand;
