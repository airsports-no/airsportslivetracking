export function getTrackValue(track, name) {
    const score = track.find((score) => {
        return score.name === name
    })
    if (score) {
        return score.value
    }
    return null
}

export function getGate(gates, gateName) {
    return gates.find((gate) => {
        return gate.gate === gateName
    })
}

export function getGateValue(gates, gateName, name) {
    const gate = getGate(gates, gateName)
    if (gate) {
        const value = gate.rules.find((score) => {
            return score.name === name
        })
        if (value) {
            return value.value
        }
    }
    return null
}
