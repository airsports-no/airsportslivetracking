const PlayingCardsList: { [key: string]: string } = {};
const suits = ['c', 'd', 'h', 's'];
const faces = ['j', 'q', 'k'];

const addSuits = (i: number | string, list: { [key: string]: string }) => {
    for (const suit of suits) {
        list[i + suit] = `${(document as any).configuration.STATIC_FILE_LOCATION}img/CardImages/${i}${suit}.svg`;
    }
}

for (let i = 1; i < 10; i++) {
    addSuits(i, PlayingCardsList);
}

for (const i of faces) {
    addSuits(i, PlayingCardsList);
}

for (const suit of suits) {
    PlayingCardsList["t" + suit] = `${(document as any).configuration.STATIC_FILE_LOCATION}img/CardImages/10${suit}.svg`;
}

for (const suit of suits) {
    PlayingCardsList["a" + suit] = `${(document as any).configuration.STATIC_FILE_LOCATION}img/CardImages/1${suit}.svg`;
}

PlayingCardsList.flipped = `${(document as any).configuration.STATIC_FILE_LOCATION}img/CardImages/b.svg`;

export default PlayingCardsList;
