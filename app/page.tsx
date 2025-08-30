// app/page.tsx
export const revalidate = 86400; // revalidate this page every 24h (ISR)

export default async function Home() {
  // Call the API route at build/revalidate time
  const res = await fetch(`${process.env.https://donosarchive.vercel.app}/api/generate`, {
    // Ensure this uses the cache set by the API (CDN/edge)
    next: { revalidate: 86400 },
  });

  const html = await res.text();

  return (
    <main style={{ padding: 24 }}>
      {/* Render the raw HTML from the Python function */}
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  );
}
