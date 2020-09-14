import React, {Component} from "react";
import axios from "axios";
import './App.css';

class App extends Component {
    constructor() {
        super();
        this.state = {
            url: '',
        }
        this.handleSubmit = this.handleSubmit.bind(this);
        this.handleChange = this.handleChange.bind(this);
    }

    handleChange(event) {
        this.setState({url: event.target.value})
    }

    handleSubmit(event) {
        axios.post("/display/url_checker", this.state.url).then(res => {
            alert(res.data)
        })
        event.preventDefault();
    }

    render() {
        return (
            <div className="App">
                <header className="App-header">
                    <form onSubmit={this.handleSubmit}>
                        <label>
                            url:
                            <input type="text" name="url" value={this.state.url} onChange={this.handleChange}/>
                        </label>
                        <input type="submit" value="Check URL"/>
                    </form>
                </header>
            </div>
        );
    }
}

export default App;