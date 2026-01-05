import React, { useState, useEffect, useRef } from 'react';
import './PlayingCard.css';
import PlayingCardsList from './PlayingCardsList';
import Draggable from 'react-draggable';
import * as ReactDOM from 'react-dom';

interface PlayingCardProps {
    card: string;
    height: number;
    flipped?: boolean;
    flippable?: boolean;
    elevated?: boolean;
    style?: React.CSSProperties;
    zIndex?: number;
    onClick?: (card: string) => void;
    onDragStart?: (card: string) => void;
    onDrag?: (card: string) => void;
    onDragStop?: (card: string) => void;
    removeCard?: (card: string, style: React.CSSProperties) => void;
    elevateOnClick?: number;
}

const PlayingCard: React.FC<PlayingCardProps> = (props) => {
    const {
        card,
        height,
        flipped = false,
        flippable = false,
        style = {},
        zIndex,
        onClick = () => {},
        onDragStart = () => {},
        onDrag = () => {},
        onDragStop = () => {},
        removeCard = () => {},
        elevateOnClick = 0,
    } = props;

    const [isFlipped, setIsFlipped] = useState(flipped || card === 'hide');
    const [cardStyle, setCardStyle] = useState<React.CSSProperties>(style);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [draggableDivStyle, setDraggableDivStyle] = useState<React.CSSProperties>({ zIndex });
    const nodeRef = useRef(null);

    useEffect(() => {
        setCardStyle(style);
        setPosition({ x: 0, y: 0 });
        setIsFlipped(flipped || card === 'hide');
    }, [style, flipped, card]);

    const handleDragStart = (e: any) => {
        setDraggableDivStyle({ zIndex: 999, position: 'fixed' });
        e.preventDefault();

        if (cardStyle && cardStyle.transform && cardStyle.transform.includes('rotate')) {
            const newTransform = cardStyle.transform.replace(/rotate\((.*?)\)/, 'rotate(0deg)');
            setCardStyle({ ...cardStyle, transform: newTransform });
        }
        
        removeCard(card, cardStyle);
        onDragStart(card);
    };

    const handleDrag = () => {
        onDrag(card);
    };

    const handleDragStop = () => {
        setDraggableDivStyle({ zIndex, position: 'relative' }); // Changed from fixed
        onDragStop(card);
    };

    const handleClick = () => {
        onClick(card);
    };

    return (
        <Draggable
            nodeRef={nodeRef}
            onStart={handleDragStart}
            onStop={handleDragStop}
            onDrag={handleDrag}
            position={position}
        >
            <div ref={nodeRef} style={draggableDivStyle}>
                <img
                    style={cardStyle}
                    height={height}
                    className='Playing-card'
                    src={isFlipped ? PlayingCardsList.flipped : PlayingCardsList[card]}
                    alt={isFlipped ? 'Hidden Card' : card}
                    onClick={handleClick}
                />
            </div>
        </Draggable>
    );
};

export default PlayingCard;
