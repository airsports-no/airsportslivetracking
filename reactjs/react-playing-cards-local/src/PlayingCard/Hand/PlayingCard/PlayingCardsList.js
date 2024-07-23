let PlayingCardsList = {};
let suits = ['c', 'd', 'h', 's'];
let faces = ['j', 'q', 'k'];

let addSuits = (i, PlayingCardsList) => {
    for (let suit of suits) {
        PlayingCardsList[i + suit] = document.configuration.STATIC_FILE_LOCATION+"img/CardImages/" + i + suit + '.svg'
    }
}

for (let i = 1; i < 10; i++) {
    addSuits(i, PlayingCardsList);
}

for (let i of faces) {
    addSuits(i, PlayingCardsList);
}

for (let suit of suits) {
    PlayingCardsList["t" + suit] = document.configuration.STATIC_FILE_LOCATION+"img/CardImages/10"+ suit + '.svg'
}

for (let suit of suits) {
    PlayingCardsList["a" + suit] = document.configuration.STATIC_FILE_LOCATION+"img/CardImages/1" + suit + '.svg'
}

PlayingCardsList.flipped = document.configuration.STATIC_FILE_LOCATION+"img/CardImages/b.svg"


export default PlayingCardsList;