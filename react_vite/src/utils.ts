
export const formatDateInterval = (startDateStr: string, endDateStr: string): string => {
    const startDate = new Date(startDateStr);
    const endDate = new Date(endDateStr);

    const options: Intl.DateTimeFormatOptions = {
        month: 'long',
        day: 'numeric',
    };

    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
        return '';
    }

    const startYear = startDate.getFullYear();
    const endYear = endDate.getFullYear();
    const startMonth = startDate.getMonth();
    const endMonth = endDate.getMonth();
    const startDay = startDate.getDate();
    const endDay = endDate.getDate();

    if (startYear === endYear && startMonth === endMonth && startDay === endDay) {
        return startDate.toLocaleDateString(undefined, { ...options, year: 'numeric' });
    }

    if (startYear === endYear && startMonth === endMonth) {
        const endOptions: Intl.DateTimeFormatOptions = { ...options, year: 'numeric' };
        return `${startDate.getDate()} - ${endDate.toLocaleDateString(undefined, endOptions)}`;
    }

    if (startYear === endYear) {
        const endOptions: Intl.DateTimeFormatOptions = { ...options, year: 'numeric' };
        return `${startDate.toLocaleDateString(undefined, options)} - ${endDate.toLocaleDateString(undefined, endOptions)}`;
    }

    const fullOptions: Intl.DateTimeFormatOptions = { ...options, year: 'numeric' };
    return `${startDate.toLocaleDateString(undefined, fullOptions)} - ${endDate.toLocaleDateString(undefined, fullOptions)}`;
};
