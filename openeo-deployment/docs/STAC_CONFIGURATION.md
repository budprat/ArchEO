# STAC Configuration for OpenEO FastAPI

This document details the STAC (SpatioTemporal Asset Catalog) configuration for the OpenEO FastAPI deployment.

---

## Table of Contents

1. [Current Configuration](#current-configuration)
2. [How STAC Integration Works](#how-stac-integration-works)
3. [Available STAC Catalogues](#available-stac-catalogues)
4. [Changing the STAC Catalogue](#changing-the-stac-catalogue)
5. [Collection Whitelisting](#collection-whitelisting)
6. [Testing STAC Connections](#testing-stac-connections)

---

## Current Configuration

**File**: `/Users/macbookpro/openeo-deployment/.env`

```bash
# Current STAC Configuration
export STAC_API_URL="https://earth-search.aws.element84.com/v1/"
```

### Current Status

| Setting | Value |
|---------|-------|
| STAC API URL | https://earth-search.aws.element84.com/v1/ |
| STAC Version | 1.0.0 |
| Collections Available | 9 |
| Whitelist | None (all collections accessible) |

### Collections Currently Available

| Collection ID | Description |
|---------------|-------------|
| `sentinel-2-l2a` | Sentinel-2 Level-2A |
| `sentinel-2-l1c` | Sentinel-2 Level-1C |
| `sentinel-2-c1-l2a` | Sentinel-2 Collection 1 Level-2A |
| `sentinel-2-pre-c1-l2a` | Sentinel-2 Pre-Collection 1 Level-2A |
| `sentinel-1-grd` | Sentinel-1 Level-1C Ground Range Detected |
| `landsat-c2-l2` | Landsat Collection 2 Level-2 |
| `cop-dem-glo-30` | Copernicus DEM GLO-30 |
| `cop-dem-glo-90` | Copernicus DEM GLO-90 |
| `naip` | National Agriculture Imagery Program |

---

## How STAC Integration Works

The OpenEO FastAPI acts as a **proxy** to an external STAC catalogue:

```
┌──────────────────┐      ┌───────────────────┐      ┌──────────────────┐
│   OpenEO Client  │─────▶│  OpenEO FastAPI   │─────▶│   STAC Catalogue │
│                  │      │  (localhost:8000) │      │   (External)     │
└──────────────────┘      └───────────────────┘      └──────────────────┘
         │                         │                         │
         │  /collections           │  GET /collections       │
         │─────────────────────────│────────────────────────▶│
         │                         │                         │
         │  ◀─────────────────────│◀────────────────────────│
         │  Collections JSON       │  Collections JSON       │
```

### Code Flow

**File**: `openeo_fastapi/client/collections.py`

```python
class CollectionRegister:
    async def _proxy_request(self, path):
        async with aiohttp.ClientSession() as client:
            async with client.get(self.settings.STAC_API_URL + path) as response:
                resp = await response.json()
                if response.status == 200:
                    return resp
```

The `STAC_API_URL` setting determines where collection/item requests are proxied.

---

## Available STAC Catalogues

### Comparison Table

| Catalogue | Collections | URL | Best For |
|-----------|-------------|-----|----------|
| **AWS Earth Search** | 9 | earth-search.aws.element84.com/v1/ | Sentinel, Landsat, DEMs |
| **Microsoft Planetary Computer** | 134 | planetarycomputer.microsoft.com/api/stac/v1/ | Climate, MODIS, comprehensive EO |
| **Copernicus Data Space** | 141 | catalogue.dataspace.copernicus.eu/stac/ | Official EU Copernicus data |
| **USGS Landsat** | 18 | landsatlook.usgs.gov/stac-server/ | Landsat archive |

---

### 1. AWS Earth Search (Current)

**URL**: `https://earth-search.aws.element84.com/v1/`

**Collections** (9):
- Sentinel-2 L1C/L2A
- Sentinel-1 GRD
- Landsat Collection 2 Level-2
- Copernicus DEM (30m/90m)
- NAIP

**Pros**:
- Free, no authentication required
- Fast, hosted on AWS
- Cloud-optimized GeoTIFFs (COGs)

**Cons**:
- Limited collection variety
- US-centric for some datasets

---

### 2. Microsoft Planetary Computer

**URL**: `https://planetarycomputer.microsoft.com/api/stac/v1/`

**Collections** (134):
- Sentinel-1/2/3
- Landsat Collection 2
- MODIS products (20+ datasets)
- ERA5 climate reanalysis
- Global DEMs (Copernicus, ALOS)
- Land cover datasets
- Climate/weather data

**Pros**:
- Largest free collection
- Comprehensive climate/environmental data
- Well-documented

**Cons**:
- Some datasets require SAS tokens for access
- May need additional authentication setup

**Key Collections**:
```
sentinel-2-l2a          - Sentinel-2 Level-2A
sentinel-1-rtc          - Sentinel-1 RTC
landsat-c2-l2           - Landsat Collection 2 Level-2
era5-pds                - ERA5 Climate Reanalysis
modis-*                 - Various MODIS products
cop-dem-glo-30          - Copernicus DEM 30m
terraclimate            - TerraClimate
```

---

### 3. Copernicus Data Space Ecosystem (CDSE)

**URL**: `https://catalogue.dataspace.copernicus.eu/stac/`

**Collections** (141):
- Complete Sentinel-1/2/3/5P archive
- Copernicus services data
- Global mosaics
- Atmospheric products

**Pros**:
- Official EU Copernicus data source
- Complete Sentinel archive
- Includes Sentinel-5P atmospheric data

**Cons**:
- May require registration for data access
- European-focused infrastructure

**Key Collections**:
```
sentinel-2-l2a              - Sentinel-2 Level-2A
sentinel-1-grd              - Sentinel-1 GRD
sentinel-3-olci-*           - Sentinel-3 OLCI products
sentinel-5p-l2-*            - Sentinel-5P atmospheric
sentinel-2-global-mosaics   - Global mosaics
```

---

### 4. USGS Landsat Look

**URL**: `https://landsatlook.usgs.gov/stac-server/`

**Collections** (18):
- Complete Landsat archive (1-9)
- Collection 2 products

**Pros**:
- Official USGS Landsat source
- Complete historical archive

**Cons**:
- Landsat-only
- May be slower for large queries

---

## Changing the STAC Catalogue

### Option 1: Edit Environment File

Edit `/Users/macbookpro/openeo-deployment/.env`:

```bash
# Change to Microsoft Planetary Computer
export STAC_API_URL="https://planetarycomputer.microsoft.com/api/stac/v1/"

# OR Copernicus Data Space
export STAC_API_URL="https://catalogue.dataspace.copernicus.eu/stac/"

# OR USGS Landsat
export STAC_API_URL="https://landsatlook.usgs.gov/stac-server/"
```

### Option 2: Restart with New Config

```bash
# Stop current server
pkill -f "uvicorn app:app"

# Edit .env file
nano /Users/macbookpro/openeo-deployment/.env

# Restart server
cd /Users/macbookpro/openeo-deployment
./start.sh
```

### Option 3: Quick Test (Temporary)

```bash
# Export new URL temporarily
export STAC_API_URL="https://planetarycomputer.microsoft.com/api/stac/v1/"

# Restart server
cd /Users/macbookpro/openeo-deployment
source .env  # Load other settings
export STAC_API_URL="https://planetarycomputer.microsoft.com/api/stac/v1/"  # Override
source venv/bin/activate
cd openeo_app
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## Collection Whitelisting

You can restrict which collections are accessible via the `STAC_COLLECTIONS_WHITELIST` setting.

### Enable Whitelist

Edit `/Users/macbookpro/openeo-deployment/.env`:

```bash
# Only expose specific collections
export STAC_COLLECTIONS_WHITELIST="sentinel-2-l2a,landsat-c2-l2,cop-dem-glo-30"
```

### How Whitelisting Works

From `openeo_fastapi/client/collections.py`:

```python
async def get_collections(self):
    # Filter collections by whitelist
    collections_list = [
        collection
        for collection in resp["collections"]
        if (
            not self.settings.STAC_COLLECTIONS_WHITELIST
            or collection["id"] in self.settings.STAC_COLLECTIONS_WHITELIST
        )
    ]
```

### Whitelist Examples

```bash
# Sentinel only
export STAC_COLLECTIONS_WHITELIST="sentinel-2-l2a,sentinel-2-l1c,sentinel-1-grd"

# Sentinel + Landsat
export STAC_COLLECTIONS_WHITELIST="sentinel-2-l2a,landsat-c2-l2"

# DEMs only
export STAC_COLLECTIONS_WHITELIST="cop-dem-glo-30,cop-dem-glo-90"

# Disable whitelist (all collections)
# Simply don't set STAC_COLLECTIONS_WHITELIST or set it empty
```

---

## Testing STAC Connections

### Test Any STAC API

```bash
# Test connectivity
curl -s "https://earth-search.aws.element84.com/v1/"

# List collections
curl -s "https://earth-search.aws.element84.com/v1/collections" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data['collections']:
    print(f\"{c['id']}: {c.get('title', '')}\")"

# Get specific collection
curl -s "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a"
```

### Test via OpenEO API

```bash
# After changing STAC_API_URL and restarting:

# List collections
curl http://localhost:8000/openeo/1.1.0/collections

# Get specific collection
curl http://localhost:8000/openeo/1.1.0/collections/sentinel-2-l2a

# Count collections
curl -s http://localhost:8000/openeo/1.1.0/collections | \
  python3 -c "import sys,json; print(len(json.load(sys.stdin)['collections']))"
```

### Verify Collection Items

```bash
# Get items from a collection
curl -s "http://localhost:8000/openeo/1.1.0/collections/sentinel-2-l2a/items" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Items returned: {len(data.get('features', []))}\")"
```

---

## Recommended Configuration

### For General Earth Observation

```bash
export STAC_API_URL="https://planetarycomputer.microsoft.com/api/stac/v1/"
```
- 134 collections
- Sentinel, Landsat, MODIS, Climate data

### For Copernicus/Sentinel Focus

```bash
export STAC_API_URL="https://catalogue.dataspace.copernicus.eu/stac/"
```
- Official EU source
- Complete Sentinel archive

### For Simplicity (Current)

```bash
export STAC_API_URL="https://earth-search.aws.element84.com/v1/"
```
- No authentication needed
- Fast AWS infrastructure
- Core datasets only

---

## Quick Reference

| Action | Command |
|--------|---------|
| Current STAC URL | `grep STAC_API_URL /Users/macbookpro/openeo-deployment/.env` |
| List collections | `curl http://localhost:8000/openeo/1.1.0/collections` |
| Count collections | `curl -s http://localhost:8000/openeo/1.1.0/collections \| python3 -c "import sys,json; print(len(json.load(sys.stdin)['collections']))"` |
| Change STAC | Edit `.env`, restart server |
| Restart server | `pkill -f uvicorn && ./start.sh` |

---

*Documentation generated on February 4, 2026*
