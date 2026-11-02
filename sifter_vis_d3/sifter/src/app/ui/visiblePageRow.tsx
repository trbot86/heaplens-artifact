'use client';
import { ReactNode, RefObject, useEffect, useRef, useState } from 'react';

// Keep the scroll geometry and page order, but do not run off-screen row
// components. The selected row stays mounted so its D3 brush survives scrolling.
export default function VisiblePageRow({ children, root, selected, expanded, address } : {
    children: ReactNode;
    root: RefObject<HTMLDivElement>;
    selected: boolean;
    expanded: boolean;
    address: string;
}) {
    const slot = useRef<HTMLDivElement>(null);
    const [visible, setVisible] = useState(false);
    useEffect(() => {
        if (!slot.current || !root.current) return;
        const observer = new IntersectionObserver(entries => {
            setVisible(entries[0].isIntersecting);
        }, { root: root.current, rootMargin: '100px 0px' });
        observer.observe(slot.current);
        return () => observer.disconnect();
    }, [root]);
    return <div ref={slot} className='pageRowSlot' data-page-address={address}>
        {(visible || selected || expanded) ? children : null}
    </div>;
}
