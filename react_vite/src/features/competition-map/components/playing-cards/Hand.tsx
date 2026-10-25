import React, { useState, useEffect, useMemo } from 'react';
import './Hand.css';
import PlayingCard from './PlayingCard';

interface HandProps {
    cards: string[];
    cardSize?: number;
    elevated?: string;
    layout?: 'fan' | 'spread' | 'stack' | 'arc';
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
        } else if (layout === 'arc') {
            // Every card turns about one point at the foot of the hand, so each shows its corner (rank and suit):
            // the step is wide enough for that, and narrower the more cards there are.
            const step = Math.min(16, 64 / Math.max(1, handLength - 1));
            return (num: number) => ({
                zIndex: num,
                transformOrigin: '50% 100%',
                transform: `translateX(-50%) rotate(${(num - (handLength - 1) / 2) * step}deg)`,
            });
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

    // The box of an arc is as wide as the turned cards need (a card is about 0.7 as wide as it is high), and as high.
    const arcStep = Math.min(16, 64 / Math.max(1, handLength - 1));
    const arcHalfAngle = ((handLength - 1) / 2) * arcStep;
    const arcWidth = Math.ceil(cardSize * (0.72 + 2 * Math.sin((arcHalfAngle * Math.PI) / 180)));
    return (
                <div
                    className={'Hand'}
                    style={layout === 'arc'
                        ? { height: Math.ceil(cardSize * 1.05), width: arcWidth, margin: 0 }
                        : { height: cardSize }}
                >
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
