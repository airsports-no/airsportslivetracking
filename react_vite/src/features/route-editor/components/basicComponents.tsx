import React from "react";

export const Loading: React.FC = () => <div className="flex justify-center"><img className="loading-lg" src={document.configuration.STATIC_FILE_LOCATION+"img/loading_airplane.gif"} alt="loading..."/></div>;
