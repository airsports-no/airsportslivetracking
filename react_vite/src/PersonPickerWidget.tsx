import React from 'react';
import { createRoot } from 'react-dom/client';
import './personpickerwidget.css';
import PersonPickerMount from './components/common/PersonPickerMount';

/**
 * Mounts the person type-ahead on server-rendered Django pages. Put
 * <div data-person-picker data-kind="user" data-search-url="..." data-target="id_user_id"></div>
 * in the page; the chosen id is written to the input whose id is data-target.
 */
document.querySelectorAll<HTMLElement>('[data-person-picker]').forEach(element => {
    const target = document.getElementById(element.dataset.target ?? '') as HTMLInputElement | null;
    createRoot(element).render(
        <PersonPickerMount
            kind={element.dataset.kind === 'person' ? 'person' : 'user'}
            searchUrl={element.dataset.searchUrl ?? ''}
            placeholder={element.dataset.placeholder}
            onSelect={id => {
                if (target) target.value = id;
            }}
        />
    );
});

export {};
