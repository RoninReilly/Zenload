/**
 * SoundCloud API Proxy Worker
 * 
 * Endpoints:
 * - GET /search?q=query&limit=4 - Search tracks
 * - GET /resolve?url=https://soundcloud.com/... - Resolve track URL
 * - GET /stream?url=https://soundcloud.com/... - Get direct stream URL
 * - GET /health - Health check
 * 
 * Deploy: wrangler deploy
 */

// Cache client_id for 1 hour
let cachedClientId = null;
let clientIdExpiry = 0;

async function getClientId() {
    const now = Date.now();
    if (cachedClientId && now < clientIdExpiry) {
        return cachedClientId;
    }

    // Fetch SoundCloud homepage to extract client_id
    const response = await fetch('https://soundcloud.com/', {
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    });

    const html = await response.text();

    // Find script URLs
    const scriptMatches = html.matchAll(/src="(https:\/\/[^"]*\.js)"/g);

    for (const match of scriptMatches) {
        const scriptUrl = match[1];
        if (scriptUrl.includes('sndcdn.com')) {
            try {
                const scriptResp = await fetch(scriptUrl);
                const scriptContent = await scriptResp.text();

                // Look for client_id pattern
                const clientIdMatch = scriptContent.match(/client_id\s*[:=]\s*["']([a-zA-Z0-9]{32})["']/);
                if (clientIdMatch) {
                    cachedClientId = clientIdMatch[1];
                    clientIdExpiry = now + 3600000; // 1 hour
                    return cachedClientId;
                }
            } catch (e) {
                continue;
            }
        }
    }

    throw new Error('Could not extract client_id');
}

async function searchTracks(query, limit = 4) {
    const clientId = await getClientId();

    const params = new URLSearchParams({
        q: query,
        client_id: clientId,
        limit: limit.toString(),
        offset: '0',
        linked_partitioning: '1'
    });

    const response = await fetch(`https://api-v2.soundcloud.com/search/tracks?${params}`, {
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
    });

    if (!response.ok) {
        throw new Error(`SoundCloud API error: ${response.status}`);
    }

    const data = await response.json();

    // Transform to simplified format
    const tracks = (data.collection || []).map(track => ({
        id: track.id,
        title: track.title,
        permalink_url: track.permalink_url,
        duration: track.duration, // milliseconds
        artwork_url: track.artwork_url,
        user: {
            username: track.user?.username,
            full_name: track.user?.full_name
        },
        media: track.media
    }));

    return tracks;
}

async function resolveUrl(url) {
    const clientId = await getClientId();

    const params = new URLSearchParams({
        url: url,
        client_id: clientId
    });

    const response = await fetch(`https://api-v2.soundcloud.com/resolve?${params}`, {
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
    });

    if (!response.ok) {
        throw new Error(`SoundCloud resolve error: ${response.status}`);
    }

    return await response.json();
}

async function getStreamUrl(trackUrl) {
    const track = await resolveUrl(trackUrl);

    if (!track.media?.transcodings) {
        throw new Error('No transcodings available');
    }

    // Prefer progressive (direct download) over HLS
    const transcodings = track.media.transcodings;
    let transcoding = transcodings.find(t => t.format?.protocol === 'progressive');
    if (!transcoding) {
        transcoding = transcodings[0];
    }

    if (!transcoding?.url) {
        throw new Error('No transcoding URL found');
    }

    // Fetch the actual stream URL
    const clientId = await getClientId();
    const streamResponse = await fetch(`${transcoding.url}?client_id=${clientId}`, {
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
    });

    if (!streamResponse.ok) {
        throw new Error(`Stream URL fetch error: ${streamResponse.status}`);
    }

    const streamData = await streamResponse.json();

    return {
        url: streamData.url,
        track: {
            id: track.id,
            title: track.title,
            permalink_url: track.permalink_url,
            duration: track.duration,
            artwork_url: track.artwork_url,
            user: {
                username: track.user?.username,
                full_name: track.user?.full_name
            }
        }
    };
}

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);
        const path = url.pathname;

        // CORS headers
        const corsHeaders = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Content-Type': 'application/json'
        };

        if (request.method === 'OPTIONS') {
            return new Response(null, { headers: corsHeaders });
        }

        try {
            if (path === '/health') {
                return new Response(JSON.stringify({ status: 'ok' }), { headers: corsHeaders });
            }

            if (path === '/search') {
                const query = url.searchParams.get('q');
                const limit = parseInt(url.searchParams.get('limit') || '4');

                if (!query) {
                    return new Response(
                        JSON.stringify({ error: 'Missing query parameter: q' }),
                        { status: 400, headers: corsHeaders }
                    );
                }

                const tracks = await searchTracks(query, limit);
                return new Response(JSON.stringify({ tracks }), { headers: corsHeaders });
            }

            if (path === '/resolve') {
                const trackUrl = url.searchParams.get('url');

                if (!trackUrl) {
                    return new Response(
                        JSON.stringify({ error: 'Missing query parameter: url' }),
                        { status: 400, headers: corsHeaders }
                    );
                }

                const track = await resolveUrl(trackUrl);
                return new Response(JSON.stringify({ track }), { headers: corsHeaders });
            }

            if (path === '/stream') {
                const trackUrl = url.searchParams.get('url');

                if (!trackUrl) {
                    return new Response(
                        JSON.stringify({ error: 'Missing query parameter: url' }),
                        { status: 400, headers: corsHeaders }
                    );
                }

                const result = await getStreamUrl(trackUrl);
                return new Response(JSON.stringify(result), { headers: corsHeaders });
            }

            return new Response(
                JSON.stringify({
                    error: 'Not found',
                    endpoints: ['/search?q=...', '/resolve?url=...', '/stream?url=...', '/health']
                }),
                { status: 404, headers: corsHeaders }
            );

        } catch (error) {
            return new Response(
                JSON.stringify({ error: error.message }),
                { status: 500, headers: corsHeaders }
            );
        }
    }
};
