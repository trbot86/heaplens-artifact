import type { Metadata } from "next";
import { inriaSans } from '@/app/ui/fonts';
import "./globals.css";

export const metadata: Metadata = {
    title: "HeapLENS — ATC 2026 artifact",
    description: "Heap Layout Evaluation and Navigation Suite",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <head>
                <meta name="viewport" content="initial-scale=1, width=device-width" />
            </head>
            <body 
                className={`${inriaSans.className} antialiased`} >
                {children}
            </body>
        </html>
    );
}
