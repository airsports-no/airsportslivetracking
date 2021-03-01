let PlayingCardsList = {};
let suits = ['c', 'd', 'h', 's'];
let faces = ['j', 'q', 'k'];

let addSuits = (i, PlayingCardsList) => {
    for (let suit of suits) {
        PlayingCardsList[i + suit] = "/static/img/CardImages/" + i + suit + '.svg'
    }
}

for (let i = 1; i < 10; i++) {
    addSuits(i, PlayingCardsList);
}

for (let i of faces) {
    addSuits(i, PlayingCardsList);
}

for (let suit of suits) {
    PlayingCardsList["t" + suit] = "/static/img/CardImages/10"+ suit + '.svg'
}

for (let suit of suits) {
    PlayingCardsList["a" + suit] = "/static/img/CardImages/1" + suit + '.svg'
}

PlayingCardsList.flipped = "/static/img/CardImages/b.svg"


export default PlayingCardsList;