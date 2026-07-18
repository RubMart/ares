/** Human-facing catalog mirror of the API YOLO class catalog (help UI). */

export type SearchCatalogEntry = {
  id: string
  labelKey: string
  examplesKey: string
}

export const SEARCH_CATALOG: SearchCatalogEntry[] = [
  {
    id: 'swimming_pool',
    labelKey: 'searchHelp.classPool',
    examplesKey: 'searchHelp.examplesPool',
  },
  {
    id: 'vehicle',
    labelKey: 'searchHelp.classVehicle',
    examplesKey: 'searchHelp.examplesVehicle',
  },
  {
    id: 'building',
    labelKey: 'searchHelp.classBuilding',
    examplesKey: 'searchHelp.examplesBuilding',
  },
  {
    id: 'photovoltaic',
    labelKey: 'searchHelp.classSolar',
    examplesKey: 'searchHelp.examplesSolar',
  },
  {
    id: 'sports',
    labelKey: 'searchHelp.classSports',
    examplesKey: 'searchHelp.examplesSports',
  },
  {
    id: 'pedestrian',
    labelKey: 'searchHelp.classPedestrian',
    examplesKey: 'searchHelp.examplesPedestrian',
  },
  {
    id: 'roundabout',
    labelKey: 'searchHelp.classRoundabout',
    examplesKey: 'searchHelp.examplesRoundabout',
  },
]
