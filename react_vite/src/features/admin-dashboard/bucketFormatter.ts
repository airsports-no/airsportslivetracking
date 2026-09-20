import { FlightStatsBin } from './api';

export const bucketFormatter = (bin: FlightStatsBin) => {
    const options: Intl.DateTimeFormatOptions =
        bin === 'hour'
            ? { month: 'short', day: 'numeric', hour: 'numeric' }
            : bin === 'day' || bin === 'week'
              ? { month: 'short', day: 'numeric' }
              : bin === 'month'
                ? { month: 'short', year: 'numeric' }
                : { year: 'numeric' };
    const formatter = new Intl.DateTimeFormat(undefined, options);
    return (isoString: string) => formatter.format(new Date(isoString));
};
