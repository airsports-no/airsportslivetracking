import { StylesConfig } from 'react-select';

export const selectStyles: StylesConfig<any, any> = {
    control: (base) => ({
        ...base,
        backgroundColor: 'var(--rs-bg)',
        color: 'var(--rs-text)',
        borderColor: 'var(--rs-border)',
        boxShadow: 'none',
        '&:hover': {
            borderColor: 'var(--rs-border)',
        }
    }),
    menu: (base) => ({
        ...base,
        backgroundColor: 'var(--rs-bg)',
        zIndex: 9999,
        border: '1px solid var(--rs-border)',
    }),
    menuList: (base) => ({
        ...base,
        backgroundColor: 'var(--rs-bg)',
    }),
    option: (base, state) => ({
        ...base,
        backgroundColor: state.isSelected 
            ? 'var(--p, #FF8C00)' 
            : state.isFocused 
                ? 'rgba(255, 140, 0, 0.2)' 
                : 'var(--rs-bg)',
        color: state.isSelected ? 'white' : 'var(--rs-text)',
        cursor: 'pointer',
        '&:active': {
            backgroundColor: 'var(--p, #FF8C00)',
        }
    }),
    input: (base) => ({
        ...base,
        color: 'var(--rs-text)',
    }),
    singleValue: (base) => ({
        ...base,
        color: 'var(--rs-text)',
    }),
    multiValue: (base) => ({
        ...base,
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        color: 'var(--rs-text)',
    }),
    multiValueLabel: (base) => ({
        ...base,
        color: 'var(--rs-text)',
    }),
    multiValueRemove: (base) => ({
        ...base,
        color: 'var(--rs-text)',
        '&:hover': {
            backgroundColor: 'rgba(255, 0, 0, 0.2)',
            color: 'white',
        }
    }),
    placeholder: (base) => ({
        ...base,
        color: 'rgba(255, 255, 255, 0.5)',
    }),
    indicatorSeparator: (base) => ({
        ...base,
        backgroundColor: 'var(--rs-border)',
    }),
    dropdownIndicator: (base) => ({
        ...base,
        color: 'var(--rs-border)',
        '&:hover': {
            color: 'var(--rs-text)',
        }
    }),
    clearIndicator: (base) => ({
        ...base,
        color: 'var(--rs-border)',
        '&:hover': {
            color: 'var(--rs-text)',
        }
    }),
};
