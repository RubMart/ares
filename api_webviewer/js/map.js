class DetectionMap {
  static _projectionsReady = false;

  static ensureProjections() {
    if (DetectionMap._projectionsReady) return;
    DetectionMap._projectionsReady = true;

    if (typeof proj4 === "undefined") {
      console.warn("proj4 no está disponible; algunas ortofotos pueden no reproyectarse.");
      return;
    }

    const defs = {
      "EPSG:25830": "+proj=utm +zone=30 +ellps=GRS80 +units=m +no_defs +type=crs",
      "EPSG:25831": "+proj=utm +zone=31 +ellps=GRS80 +units=m +no_defs +type=crs",
      "EPSG:4326": "+proj=longlat +datum=WGS84 +no_defs +type=crs",
    };

    Object.entries(defs).forEach(([code, definition]) => {
      if (!proj4.defs(code)) {
        proj4.defs(code, definition);
      }
    });

    ol.proj.proj4.register(proj4);
  }

  constructor(targetId, popupId) {
    DetectionMap.ensureProjections();

    this.popupEl = document.getElementById(popupId);
    this.vectorSource = new ol.source.Vector();
    this.referenceSource = new ol.source.Vector();
    this.selectedFeatureIndex = null;
    this.onFeatureSelect = null;

    this.vectorLayer = new ol.layer.Vector({
      source: this.vectorSource,
      style: (feature) => this.styleForFeature(feature),
    });

    this.referenceLayer = new ol.layer.Vector({
      source: this.referenceSource,
      style: () =>
        new ol.style.Style({
          fill: new ol.style.Fill({ color: "rgba(249, 115, 22, 0.18)" }),
          stroke: new ol.style.Stroke({
            color: "rgba(234, 88, 12, 0.9)",
            width: 2,
            lineDash: [6, 4],
          }),
        }),
      zIndex: 5,
    });

    this.baseLayer = new ol.layer.Tile({ source: new ol.source.OSM() });
    this.cogLayer = null;
    this.cogSource = null;
    this.onCogError = null;

    this.map = new ol.Map({
      target: targetId,
      layers: [
        this.baseLayer,
        this.referenceLayer,
        this.vectorLayer,
      ],
      view: new ol.View({
        center: [0, 0],
        zoom: 2,
        projection: "EPSG:3857",
      }),
    });

    this.geoJsonFormat = new ol.format.GeoJSON({
      dataProjection: "EPSG:3857",
      featureProjection: "EPSG:3857",
    });

    this.map.on("pointermove", (event) => {
      const hit = this.map.forEachFeatureAtPixel(
        event.pixel,
        (feature) => (feature.get("filtered") ? undefined : true),
        { layerFilter: (layer) => layer === this.vectorLayer }
      );
      this.map.getTargetElement().style.cursor = hit ? "pointer" : "";
    });

    this.map.on("click", (event) => {
      const feature = this.map.forEachFeatureAtPixel(
        event.pixel,
        (f) => (f.get("filtered") ? undefined : f),
        { layerFilter: (layer) => layer === this.vectorLayer }
      );

      if (feature) {
        const featureIndex = feature.get("featureIndex");
        this.selectFeature(featureIndex, { zoom: false });
        this.showPopup(event.coordinate, feature.getProperties());
      } else {
        this.hidePopup();
      }
    });
  }

  static FILL_OPACITY = 0.28;
  static STROKE_OPACITY = 0.55;

  static similarityColor(similarity) {
    const t = Math.max(0, Math.min(1, similarity ?? 0));
    const r = Math.round(34 + (220 - 34) * t);
    const g = Math.round(197 - (197 - 38) * t);
    const b = Math.round(94 - (94 - 38) * t);
    return `rgba(${r}, ${g}, ${b}, ${DetectionMap.FILL_OPACITY})`;
  }

  styleForFeature(feature) {
    if (feature.get("filtered")) {
      return null;
    }

    const similarity = feature.get("similarity");
    const color = DetectionMap.similarityColor(similarity);
    const isSelected = feature.get("featureIndex") === this.selectedFeatureIndex;

    return new ol.style.Style({
      fill: new ol.style.Fill({ color }),
      stroke: new ol.style.Stroke({
        color: isSelected
          ? "rgba(37, 99, 235, 0.95)"
          : `rgba(15, 23, 42, ${DetectionMap.STROKE_OPACITY})`,
        width: isSelected ? 3 : 1.5,
      }),
    });
  }

  getFeatureByIndex(index) {
    return this.vectorSource.getFeatures().find((feature) => feature.get("featureIndex") === index);
  }

  selectFeature(index, options = {}) {
    const { zoom = true, showPopup = true } = options;
    const feature = this.getFeatureByIndex(index);
    if (!feature || feature.get("filtered")) return false;

    this.selectedFeatureIndex = index;
    this.vectorLayer.changed();

    const showFeaturePopup = () => {
      if (!showPopup) {
        this.hidePopup();
        return;
      }
      const geometry = feature.getGeometry();
      if (!geometry) return;
      const center = ol.extent.getCenter(geometry.getExtent());
      this.showPopup(center, feature.getProperties());
    };

    if (zoom) {
      const extent = feature.getGeometry()?.getExtent();
      if (extent?.every(Number.isFinite)) {
        this.map.getView().fit(extent, {
          padding: [60, 60, 60, 60],
          maxZoom: 18,
          duration: 400,
        });
        this.map.once("moveend", showFeaturePopup);
      } else {
        showFeaturePopup();
      }
    } else {
      showFeaturePopup();
    }

    if (this.onFeatureSelect) {
      this.onFeatureSelect(index);
    }

    return true;
  }

  static isHttpCogUrl(url) {
    return typeof url === "string" && /^https?:\/\//i.test(url.trim());
  }

  removeCogLayer() {
    if (!this.cogLayer) return;
    this.map.removeLayer(this.cogLayer);
    this.cogLayer = null;
    this.cogSource = null;
  }

  loadCogLayer(cogUrl, options = {}) {
    const { opacity = 1, fitBbox = null } = options;
    this.removeCogLayer();

    if (!DetectionMap.isHttpCogUrl(cogUrl)) {
      return Promise.resolve(false);
    }

    const url = cogUrl.trim();
    this.cogSource = new ol.source.GeoTIFF({
      sources: [{ url }],
      convertToRGB: true,
      interpolate: true,
    });

    this.cogLayer = new ol.layer.WebGLTile({
      source: this.cogSource,
      opacity,
    });

    this.map.getLayers().insertAt(1, this.cogLayer);

    return this.cogSource
      .getView()
      .then((viewOptions) => {
        if (fitBbox) {
          this.fitCogView(viewOptions, fitBbox);
        }
        this.refreshMapSize();
        return true;
      })
      .catch((error) => {
        if (fitBbox) {
          this.fitToGeoJsonExtent(fitBbox);
        }
        this.refreshMapSize();
        if (this.onCogError) {
          this.onCogError(error, url);
        }
        return false;
      });
  }

  fitCogView(viewOptions, fallbackBbox = null) {
    const extent = viewOptions?.extent;
    const projection = viewOptions?.projection;

    if (extent?.every(Number.isFinite)) {
      const mapExtent =
        projection && projection.getCode() !== "EPSG:3857"
          ? ol.proj.transformExtent(extent, projection, "EPSG:3857")
          : extent;

      this.map.getView().fit(mapExtent, {
        padding: [40, 40, 40, 40],
        maxZoom: 19,
      });
      return;
    }

    if (fallbackBbox) {
      this.fitToGeoJsonExtent(fallbackBbox);
    }
  }

  fitToGeoJsonExtent(geoJsonGeometry) {
    const geometry = this.geoJsonFormat.readGeometry(geoJsonGeometry, {
      dataProjection: "EPSG:3857",
      featureProjection: "EPSG:3857",
    });
    if (!geometry) return;

    const extent = geometry.getExtent();
    if (!extent?.every(Number.isFinite)) return;

    this.map.getView().fit(extent, {
      padding: [40, 40, 40, 40],
      maxZoom: 19,
    });
  }

  clear() {
    this.vectorSource.clear();
    this.referenceSource.clear();
    this.selectedFeatureIndex = null;
    this.hidePopup();
  }

  loadGeoJson(featureCollection) {
    this.clear();

    if (!featureCollection?.features?.length) {
      this.loadReferenceFeatures(featureCollection?.metadata?.reference_features);
      return;
    }

    const features = this.geoJsonFormat.readFeatures(featureCollection);
    features.forEach((feature, index) => feature.set("featureIndex", index));
    this.vectorSource.addFeatures(features);
    this.loadReferenceFeatures(featureCollection?.metadata?.reference_features);
  }

  loadReferenceFeatures(referenceCollection) {
    this.referenceSource.clear();
    if (!referenceCollection?.features?.length) return;

    const features = this.geoJsonFormat.readFeatures(referenceCollection);
    features.forEach((feature) => feature.set("role", "reference"));
    this.referenceSource.addFeatures(features);
  }

  setFilteredIndices(visibleIndices) {
    this.vectorSource.getFeatures().forEach((feature) => {
      const index = feature.get("featureIndex");
      feature.set("filtered", !visibleIndices.has(index));
    });
    this.vectorLayer.changed();
  }

  showPopup(coordinate, props) {
    const lines = [
      `<strong>${props.clase_yolo ?? "—"}</strong>`,
      `similarity: ${props.similarity ?? "—"}`,
      `confianza: ${props.confianza ?? "—"}`,
    ];
    if (props.distance_to_reference_m != null && props.distance_to_reference_m !== "") {
      lines.push(`distancia: ${Number(props.distance_to_reference_m).toFixed(1)} m`);
    }
    lines.push(`layer: ${props.layer ?? "—"}`);
    lines.push(`tile_id: ${props.tile_id ?? "—"}`);

    this.popupEl.innerHTML = lines.join("<br>");

    const pixel = this.map.getPixelFromCoordinate(coordinate);
    if (!pixel) {
      this.popupEl.classList.add("hidden");
      return;
    }

    this.popupEl.classList.remove("hidden");
    this.popupEl.style.left = `${pixel[0] + 12}px`;
    this.popupEl.style.top = `${pixel[1] - 8}px`;
  }

  hidePopup() {
    this.popupEl.classList.add("hidden");
  }

  refreshMapSize() {
    this.map.updateSize();
    if (this.cogLayer) {
      this.cogLayer.changed();
    }
    requestAnimationFrame(() => this.map.updateSize());
  }

  updateSize() {
    this.refreshMapSize();
  }
}
