/**
 * Client-Side Container Mock Telemetry Engine
 * Provides dual format payloads (Standard Enterprise JSON & Lightweight Mobile-App JSON)
 * Zero network API requests required.
 */

export const CONTAINER_SAMPLES = [
  {
    container_no: "MSMU6484830",
    carrier_name: "Mediterranean Shipping Company (MSC)",
    carrier_code: "MSCU",
    status: "IN_TRANSIT",
    origin_name: "Jebel Ali Port, UAE (AEJEA)",
    destination_name: "Port of Rotterdam, Netherlands (NLRTM)",
    vessel: "MSC DIANA / Voyage MS2610W",
  },
  {
    container_no: "ONEU2157736",
    carrier_name: "Ocean Network Express (ONE)",
    carrier_code: "ONEY",
    status: "DELIVERED",
    origin_name: "Port of Singapore (SGSIN)",
    destination_name: "Port of Los Angeles, USA (USLAX)",
    vessel: "ONE HARBOUR / Voyage 038E",
  },
  {
    container_no: "MEDU9650838",
    carrier_name: "Mediterranean Shipping Company (MSC)",
    carrier_code: "MSCU",
    status: "PORT_ARRIVED",
    origin_name: "Shanghai Yangshan Port, China (CNSHG)",
    destination_name: "Port of Antwerp, Belgium (BEANR)",
    vessel: "MSC GULSUN / Voyage FE402W",
  },
  {
    container_no: "MAEU1234567",
    carrier_name: "Maersk Line (A.P. Moller - Maersk)",
    carrier_code: "MAEU",
    status: "GATE_IN",
    origin_name: "Busan Newport, South Korea (KRPUS)",
    destination_name: "Port of Hamburg, Germany (DEHAM)",
    vessel: "MAERSK MC-KINNEY MOLLER / Voyage 261W",
  },
];

const MOCK_DATA_STORE = {
  MSMU6484830: {
    standard: {
      tracking_number: "MSMU6484830",
      container_no: "MSMU6484830",
      mode: "SEA",
      carrier: {
        code: "MSCU",
        prefix: "MSM",
        name: "Mediterranean Shipping Company (MSC)",
        mode: "SEA",
        primary_provider: "msc_official_direct",
        fallback_providers: ["ldb_container", "searates_broker"]
      },
      status: "IN_TRANSIT",
      message: "Vessel in transit to Port of Rotterdam via Suez Checkpoint",
      origin: "Jebel Ali, United Arab Emirates (AEJEA)",
      destination: "Port of Rotterdam, Netherlands (NLRTM)",
      origin_coordinates: {
        lat: 24.9857,
        lng: 55.0273,
        matched_code: "AEJEA",
        matched_name: "Jebel Ali Port",
        location_type: "SEAPORT",
        city: "Dubai",
        country: "United Arab Emirates"
      },
      destination_coordinates: {
        lat: 51.9554,
        lng: 4.1332,
        matched_code: "NLRTM",
        matched_name: "Port of Rotterdam",
        location_type: "SEAPORT",
        city: "Rotterdam",
        country: "Netherlands"
      },
      pieces: 1,
      weight: {
        value: 24500.0,
        unit: "KGS"
      },
      volume: 67.5,
      vessel_name: "MSC DIANA",
      latest_event: {
        station: "Suez Canal Transit (EGSCA)",
        status_code: "DEPARTED",
        status_message: "Vessel departed Suez transit checkpoint en route to Rotterdam",
        event_time: "2026-10-27T08:30:00Z",
        flight_info: "Voyage MS2610W",
        pieces: 1,
        weight: 24500.0,
        raw_status: "DEPARTED_CHECKPOINT",
        coordinates: {
          lat: 30.5852,
          lng: 32.2654,
          matched_code: "EGSCA",
          matched_name: "Suez Canal Transit Checkpoint",
          location_type: "SEAPORT",
          city: "Ismailia",
          country: "Egypt"
        }
      },
      events: [
        {
          station: "Suez Canal Transit (EGSCA)",
          status_code: "DEPARTED",
          status_message: "Vessel departed Suez transit checkpoint en route to Rotterdam",
          event_time: "2026-10-27T08:30:00Z",
          flight_info: "Voyage MS2610W",
          pieces: 1,
          weight: 24500.0,
          coordinates: {
            lat: 30.5852,
            lng: 32.2654,
            matched_code: "EGSCA",
            matched_name: "Suez Canal Transit Checkpoint",
            location_type: "SEAPORT",
            city: "Ismailia",
            country: "Egypt"
          }
        },
        {
          station: "Port of Salalah (OMSLL)",
          status_code: "TRANSSHIPMENT",
          status_message: "Container transshipped onto mother vessel MSC DIANA",
          event_time: "2026-10-24T14:15:00Z",
          flight_info: "Voyage MS2610W",
          pieces: 1,
          weight: 24500.0,
          coordinates: {
            lat: 16.9401,
            lng: 54.0089,
            matched_code: "OMSLL",
            matched_name: "Port of Salalah",
            location_type: "SEAPORT",
            city: "Salalah",
            country: "Oman"
          }
        },
        {
          station: "Jebel Ali Port (AEJEA)",
          status_code: "LOADED",
          status_message: "Loaded on board feeder vessel at Jebel Ali Terminal 2",
          event_time: "2026-10-21T19:40:00Z",
          flight_info: "Voyage FD102",
          pieces: 1,
          weight: 24500.0,
          coordinates: {
            lat: 24.9857,
            lng: 55.0273,
            matched_code: "AEJEA",
            matched_name: "Jebel Ali Port",
            location_type: "SEAPORT",
            city: "Dubai",
            country: "United Arab Emirates"
          }
        },
        {
          station: "Jebel Ali Port (AEJEA)",
          status_code: "GATE_IN",
          status_message: "Full container received at terminal gate",
          event_time: "2026-10-19T11:20:00Z",
          flight_info: null,
          pieces: 1,
          weight: 24500.0,
          coordinates: {
            lat: 24.9857,
            lng: 55.0273,
            matched_code: "AEJEA",
            matched_name: "Jebel Ali Port",
            location_type: "SEAPORT",
            city: "Dubai",
            country: "United Arab Emirates"
          }
        }
      ],
      agent_trail: {
        detected_mode: "SEA",
        carrier_identified: "MSC (Mediterranean Shipping Company)",
        carrier_code: "MSCU",
        provider_plan: ["msc_official_direct", "ldb_container"],
        attempts: [
          {
            provider_name: "msc_official_direct",
            status: "SUCCESS",
            http_status: 200,
            latency_ms: 312.4
          }
        ],
        final_provider_used: "msc_official_direct"
      }
    },
    mobileApp: {
      awbNumber: "MSMU6484830",
      mode: "SEA",
      carrier: "Mediterranean Shipping Company (MSC)",
      carrierCode: "MSCU",
      trackingStatus: "IN_TRANSIT",
      message: "Vessel in transit to Port of Rotterdam via Suez Checkpoint",
      origin: "Jebel Ali, United Arab Emirates (AEJEA)",
      destination: "Port of Rotterdam, Netherlands (NLRTM)",
      originCoordinates: {
        lat: 24.9857,
        lng: 55.0273,
        matched_code: "AEJEA",
        matched_name: "Jebel Ali Port",
        location_type: "SEAPORT",
        city: "Dubai",
        country: "United Arab Emirates"
      },
      destinationCoordinates: {
        lat: 51.9554,
        lng: 4.1332,
        matched_code: "NLRTM",
        matched_name: "Port of Rotterdam",
        location_type: "SEAPORT",
        city: "Rotterdam",
        country: "Netherlands"
      },
      pieces: "1",
      weight: "24500.0",
      weightUnit: "KGS",
      volume: 67.5,
      latestEvent: "Vessel departed Suez transit checkpoint en route to Rotterdam",
      latestStation: "Suez Canal Transit (EGSCA)",
      latestTime: "2026-10-27T08:30:00Z",
      events: [
        {
          station: "Suez Canal Transit (EGSCA)",
          status: "Vessel departed Suez transit checkpoint en route to Rotterdam",
          statusCode: "DEPARTED",
          time: "2026-10-27T08:30:00Z",
          flight: "Voyage MS2610W",
          pieces: "1",
          weight: "24500.0",
          lat: 30.5852,
          lng: 32.2654,
          locationName: "Suez Canal Transit Checkpoint"
        },
        {
          station: "Port of Salalah (OMSLL)",
          status: "Container transshipped onto mother vessel MSC DIANA",
          statusCode: "TRANSSHIPMENT",
          time: "2026-10-24T14:15:00Z",
          flight: "Voyage MS2610W",
          pieces: "1",
          weight: "24500.0",
          lat: 16.9401,
          lng: 54.0089,
          locationName: "Port of Salalah"
        },
        {
          station: "Jebel Ali Port (AEJEA)",
          status: "Loaded on board feeder vessel at Jebel Ali Terminal 2",
          statusCode: "LOADED",
          time: "2026-10-21T19:40:00Z",
          flight: "Voyage FD102",
          pieces: "1",
          weight: "24500.0",
          lat: 24.9857,
          lng: 55.0273,
          locationName: "Jebel Ali Port"
        },
        {
          station: "Jebel Ali Port (AEJEA)",
          status: "Full container received at terminal gate",
          statusCode: "GATE_IN",
          time: "2026-10-19T11:20:00Z",
          flight: null,
          pieces: "1",
          weight: "24500.0",
          lat: 24.9857,
          lng: 55.0273,
          locationName: "Jebel Ali Port"
        }
      ]
    }
  },

  ONEU2157736: {
    standard: {
      tracking_number: "ONEU2157736",
      container_no: "ONEU2157736",
      mode: "SEA",
      carrier: {
        code: "ONEY",
        prefix: "ONE",
        name: "Ocean Network Express (ONE)",
        mode: "SEA",
        primary_provider: "one_line_official",
        fallback_providers: ["ldb_container"]
      },
      status: "DELIVERED",
      message: "Empty Container Returned to Customer Depot",
      origin: "Port of Singapore (SGSIN)",
      destination: "Port of Los Angeles, United States (USLAX)",
      origin_coordinates: {
        lat: 1.2644,
        lng: 103.8222,
        matched_code: "SGSIN",
        matched_name: "Port of Singapore",
        location_type: "SEAPORT",
        city: "Singapore",
        country: "Singapore"
      },
      destination_coordinates: {
        lat: 33.7432,
        lng: -118.2673,
        matched_code: "USLAX",
        matched_name: "Port of Los Angeles",
        location_type: "SEAPORT",
        city: "Los Angeles",
        country: "United States"
      },
      pieces: 1,
      weight: {
        value: 19800.0,
        unit: "KGS"
      },
      volume: 76.2,
      vessel_name: "ONE HARBOUR",
      latest_event: {
        station: "Los Angeles Depot (USLAX)",
        status_code: "EMPTY_RETURN",
        status_message: "Empty container returned from customer to inland terminal yard",
        event_time: "2026-10-26T16:00:00Z",
        flight_info: null,
        pieces: 1,
        weight: 19800.0,
        raw_status: "EMPTY_RETURNED",
        coordinates: {
          lat: 33.7432,
          lng: -118.2673,
          matched_code: "USLAX",
          matched_name: "Port of Los Angeles Depot",
          location_type: "SEAPORT",
          city: "Los Angeles",
          country: "United States"
        }
      },
      events: [
        {
          station: "Los Angeles Depot (USLAX)",
          status_code: "EMPTY_RETURN",
          status_message: "Empty container returned from customer to inland terminal yard",
          event_time: "2026-10-26T16:00:00Z",
          flight_info: null,
          pieces: 1,
          weight: 19800.0,
          coordinates: {
            lat: 33.7432,
            lng: -118.2673,
            matched_code: "USLAX",
            matched_name: "Port of Los Angeles Depot",
            location_type: "SEAPORT",
            city: "Los Angeles",
            country: "United States"
          }
        },
        {
          station: "Port of Los Angeles (USLAX)",
          status_code: "GATE_OUT",
          status_message: "Gate out loaded for delivery to consignee warehouse",
          event_time: "2026-10-25T09:15:00Z",
          flight_info: "Truck 9021",
          pieces: 1,
          weight: 19800.0,
          coordinates: {
            lat: 33.7432,
            lng: -118.2673,
            matched_code: "USLAX",
            matched_name: "Port of Los Angeles",
            location_type: "SEAPORT",
            city: "Los Angeles",
            country: "United States"
          }
        },
        {
          station: "Port of Los Angeles (USLAX)",
          status_code: "DISCHARGED",
          status_message: "Import container discharged from vessel ONE HARBOUR",
          event_time: "2026-10-24T18:45:00Z",
          flight_info: "Voyage 038E",
          pieces: 1,
          weight: 19800.0,
          coordinates: {
            lat: 33.7432,
            lng: -118.2673,
            matched_code: "USLAX",
            matched_name: "Port of Los Angeles",
            location_type: "SEAPORT",
            city: "Los Angeles",
            country: "United States"
          }
        },
        {
          station: "Port of Singapore (SGSIN)",
          status_code: "DEPARTED",
          status_message: "Vessel departed Port of Singapore for Pacific crossing",
          event_time: "2026-10-10T14:00:00Z",
          flight_info: "Voyage 038E",
          pieces: 1,
          weight: 19800.0,
          coordinates: {
            lat: 1.2644,
            lng: 103.8222,
            matched_code: "SGSIN",
            matched_name: "Port of Singapore",
            location_type: "SEAPORT",
            city: "Singapore",
            country: "Singapore"
          }
        },
        {
          station: "Port of Singapore (SGSIN)",
          status_code: "LOADED",
          status_message: "Container loaded onto vessel ONE HARBOUR at PSA Terminal 4",
          event_time: "2026-10-08T10:30:00Z",
          flight_info: "Voyage 038E",
          pieces: 1,
          weight: 19800.0,
          coordinates: {
            lat: 1.2644,
            lng: 103.8222,
            matched_code: "SGSIN",
            matched_name: "Port of Singapore",
            location_type: "SEAPORT",
            city: "Singapore",
            country: "Singapore"
          }
        }
      ],
      agent_trail: {
        detected_mode: "SEA",
        carrier_identified: "Ocean Network Express (ONE)",
        carrier_code: "ONEY",
        provider_plan: ["one_line_official", "ldb_container"],
        attempts: [
          {
            provider_name: "one_line_official",
            status: "SUCCESS",
            http_status: 200,
            latency_ms: 278.1
          }
        ],
        final_provider_used: "one_line_official"
      }
    },
    mobileApp: {
      awbNumber: "ONEU2157736",
      mode: "SEA",
      carrier: "Ocean Network Express (ONE)",
      carrierCode: "ONEY",
      trackingStatus: "DELIVERED",
      message: "Empty Container Returned to Customer Depot",
      origin: "Port of Singapore (SGSIN)",
      destination: "Port of Los Angeles, United States (USLAX)",
      originCoordinates: {
        lat: 1.2644,
        lng: 103.8222,
        matched_code: "SGSIN",
        matched_name: "Port of Singapore",
        location_type: "SEAPORT",
        city: "Singapore",
        country: "Singapore"
      },
      destinationCoordinates: {
        lat: 33.7432,
        lng: -118.2673,
        matched_code: "USLAX",
        matched_name: "Port of Los Angeles",
        location_type: "SEAPORT",
        city: "Los Angeles",
        country: "United States"
      },
      pieces: "1",
      weight: "19800.0",
      weightUnit: "KGS",
      volume: 76.2,
      latestEvent: "Empty container returned from customer to inland terminal yard",
      latestStation: "Los Angeles Depot (USLAX)",
      latestTime: "2026-10-26T16:00:00Z",
      events: [
        {
          station: "Los Angeles Depot (USLAX)",
          status: "Empty container returned from customer to inland terminal yard",
          statusCode: "EMPTY_RETURN",
          time: "2026-10-26T16:00:00Z",
          flight: null,
          pieces: "1",
          weight: "19800.0",
          lat: 33.7432,
          lng: -118.2673,
          locationName: "Port of Los Angeles Depot"
        },
        {
          station: "Port of Los Angeles (USLAX)",
          status: "Gate out loaded for delivery to consignee warehouse",
          statusCode: "GATE_OUT",
          time: "2026-10-25T09:15:00Z",
          flight: "Truck 9021",
          pieces: "1",
          weight: "19800.0",
          lat: 33.7432,
          lng: -118.2673,
          locationName: "Port of Los Angeles"
        },
        {
          station: "Port of Los Angeles (USLAX)",
          status: "Import container discharged from vessel ONE HARBOUR",
          statusCode: "DISCHARGED",
          time: "2026-10-24T18:45:00Z",
          flight: "Voyage 038E",
          pieces: "1",
          weight: "19800.0",
          lat: 33.7432,
          lng: -118.2673,
          locationName: "Port of Los Angeles"
        },
        {
          station: "Port of Singapore (SGSIN)",
          status: "Vessel departed Port of Singapore for Pacific crossing",
          statusCode: "DEPARTED",
          time: "2026-10-10T14:00:00Z",
          flight: "Voyage 038E",
          pieces: "1",
          weight: "19800.0",
          lat: 1.2644,
          lng: 103.8222,
          locationName: "Port of Singapore"
        },
        {
          station: "Port of Singapore (SGSIN)",
          status: "Container loaded onto vessel ONE HARBOUR at PSA Terminal 4",
          statusCode: "LOADED",
          time: "2026-10-08T10:30:00Z",
          flight: "Voyage 038E",
          pieces: "1",
          weight: "19800.0",
          lat: 1.2644,
          lng: 103.8222,
          locationName: "Port of Singapore"
        }
      ]
    }
  },

  MEDU9650838: {
    standard: {
      tracking_number: "MEDU9650838",
      container_no: "MEDU9650838",
      mode: "SEA",
      carrier: {
        code: "MSCU",
        prefix: "MED",
        name: "Mediterranean Shipping Company (MSC)",
        mode: "SEA",
        primary_provider: "msc_official_direct",
        fallback_providers: ["ldb_container"]
      },
      status: "PORT_ARRIVED",
      message: "Vessel berthed at Antwerp Gateway Terminal",
      origin: "Shanghai Yangshan Port, China (CNSHG)",
      destination: "Port of Antwerp, Belgium (BEANR)",
      origin_coordinates: {
        lat: 30.6278,
        lng: 122.0645,
        matched_code: "CNSHG",
        matched_name: "Port of Shanghai (Yangshan)",
        location_type: "SEAPORT",
        city: "Shanghai",
        country: "China"
      },
      destination_coordinates: {
        lat: 51.2789,
        lng: 4.3167,
        matched_code: "BEANR",
        matched_name: "Port of Antwerp",
        location_type: "SEAPORT",
        city: "Antwerp",
        country: "Belgium"
      },
      pieces: 1,
      weight: {
        value: 28200.0,
        unit: "KGS"
      },
      volume: 68.0,
      vessel_name: "MSC GULSUN",
      latest_event: {
        station: "Port of Antwerp (BEANR)",
        status_code: "BERTHED",
        status_message: "Vessel berthed safely at Antwerp Gateway Quay 1700",
        event_time: "2026-10-27T04:10:00Z",
        flight_info: "Voyage FE402W",
        pieces: 1,
        weight: 28200.0,
        raw_status: "BERTHED",
        coordinates: {
          lat: 51.2789,
          lng: 4.3167,
          matched_code: "BEANR",
          matched_name: "Port of Antwerp",
          location_type: "SEAPORT",
          city: "Antwerp",
          country: "Belgium"
        }
      },
      events: [
        {
          station: "Port of Antwerp (BEANR)",
          status_code: "BERTHED",
          status_message: "Vessel berthed safely at Antwerp Gateway Quay 1700",
          event_time: "2026-10-27T04:10:00Z",
          flight_info: "Voyage FE402W",
          pieces: 1,
          weight: 28200.0,
          coordinates: {
            lat: 51.2789,
            lng: 4.3167,
            matched_code: "BEANR",
            matched_name: "Port of Antwerp",
            location_type: "SEAPORT",
            city: "Antwerp",
            country: "Belgium"
          }
        },
        {
          station: "Port of Antwerp Approach (BEANR)",
          status_code: "PILOT_ONBOARD",
          status_message: "Inbound sea pilot boarded at Wandelaar station",
          event_time: "2026-10-26T21:40:00Z",
          flight_info: "Voyage FE402W",
          pieces: 1,
          weight: 28200.0,
          coordinates: {
            lat: 51.37,
            lng: 3.01,
            matched_code: "BEANR",
            matched_name: "Wandelaar Pilot Station",
            location_type: "SEAPORT",
            city: "Zeebrugge",
            country: "Belgium"
          }
        },
        {
          station: "Bab el-Mandeb Transit (DJJIB)",
          status_code: "PASSAGE",
          status_message: "Passed naval escort checkpoint Bab el-Mandeb",
          event_time: "2026-10-14T08:00:00Z",
          flight_info: "Voyage FE402W",
          pieces: 1,
          weight: 28200.0,
          coordinates: {
            lat: 11.595,
            lng: 43.148,
            matched_code: "DJJIB",
            matched_name: "Bab el-Mandeb Checkpoint",
            location_type: "SEAPORT",
            city: "Djibouti",
            country: "Djibouti"
          }
        },
        {
          station: "Port of Shanghai (CNSHG)",
          status_code: "DEPARTED",
          status_message: "Vessel departed Shanghai Yangshan Terminal 3",
          event_time: "2026-10-02T22:15:00Z",
          flight_info: "Voyage FE402W",
          pieces: 1,
          weight: 28200.0,
          coordinates: {
            lat: 30.6278,
            lng: 122.0645,
            matched_code: "CNSHG",
            matched_name: "Port of Shanghai (Yangshan)",
            location_type: "SEAPORT",
            city: "Shanghai",
            country: "China"
          }
        }
      ],
      agent_trail: {
        detected_mode: "SEA",
        carrier_identified: "MSC (Mediterranean Shipping Company)",
        carrier_code: "MSCU",
        provider_plan: ["msc_official_direct", "searates_broker"],
        attempts: [
          {
            provider_name: "msc_official_direct",
            status: "SUCCESS",
            http_status: 200,
            latency_ms: 325.0
          }
        ],
        final_provider_used: "msc_official_direct"
      }
    },
    mobileApp: {
      awbNumber: "MEDU9650838",
      mode: "SEA",
      carrier: "Mediterranean Shipping Company (MSC)",
      carrierCode: "MSCU",
      trackingStatus: "PORT_ARRIVED",
      message: "Vessel berthed at Antwerp Gateway Terminal",
      origin: "Shanghai Yangshan Port, China (CNSHG)",
      destination: "Port of Antwerp, Belgium (BEANR)",
      originCoordinates: {
        lat: 30.6278,
        lng: 122.0645,
        matched_code: "CNSHG",
        matched_name: "Port of Shanghai (Yangshan)",
        location_type: "SEAPORT",
        city: "Shanghai",
        country: "China"
      },
      destinationCoordinates: {
        lat: 51.2789,
        lng: 4.3167,
        matched_code: "BEANR",
        matched_name: "Port of Antwerp",
        location_type: "SEAPORT",
        city: "Antwerp",
        country: "Belgium"
      },
      pieces: "1",
      weight: "28200.0",
      weightUnit: "KGS",
      volume: 68.0,
      latestEvent: "Vessel berthed safely at Antwerp Gateway Quay 1700",
      latestStation: "Port of Antwerp (BEANR)",
      latestTime: "2026-10-27T04:10:00Z",
      events: [
        {
          station: "Port of Antwerp (BEANR)",
          status: "Vessel berthed safely at Antwerp Gateway Quay 1700",
          statusCode: "BERTHED",
          time: "2026-10-27T04:10:00Z",
          flight: "Voyage FE402W",
          pieces: "1",
          weight: "28200.0",
          lat: 51.2789,
          lng: 4.3167,
          locationName: "Port of Antwerp"
        },
        {
          station: "Port of Antwerp Approach (BEANR)",
          status: "Inbound sea pilot boarded at Wandelaar station",
          statusCode: "PILOT_ONBOARD",
          time: "2026-10-26T21:40:00Z",
          flight: "Voyage FE402W",
          pieces: "1",
          weight: "28200.0",
          lat: 51.37,
          lng: 3.01,
          locationName: "Wandelaar Pilot Station"
        },
        {
          station: "Bab el-Mandeb Transit (DJJIB)",
          status: "Passed naval escort checkpoint Bab el-Mandeb",
          statusCode: "PASSAGE",
          time: "2026-10-14T08:00:00Z",
          flight: "Voyage FE402W",
          pieces: "1",
          weight: "28200.0",
          lat: 11.595,
          lng: 43.148,
          locationName: "Bab el-Mandeb Checkpoint"
        },
        {
          station: "Port of Shanghai (CNSHG)",
          status: "Vessel departed Shanghai Yangshan Terminal 3",
          statusCode: "DEPARTED",
          time: "2026-10-02T22:15:00Z",
          flight: "Voyage FE402W",
          pieces: "1",
          weight: "28200.0",
          lat: 30.6278,
          lng: 122.0645,
          locationName: "Port of Shanghai (Yangshan)"
        }
      ]
    }
  },

  MAEU1234567: {
    standard: {
      tracking_number: "MAEU1234567",
      container_no: "MAEU1234567",
      mode: "SEA",
      carrier: {
        code: "MAEU",
        prefix: "MAE",
        name: "Maersk Line (A.P. Moller - Maersk)",
        mode: "SEA",
        primary_provider: "maersk_official_direct",
        fallback_providers: ["ldb_container"]
      },
      status: "GATE_IN",
      message: "Container gated in at Busan Newport Terminal",
      origin: "Port of Busan, South Korea (KRPUS)",
      destination: "Port of Hamburg, Germany (DEHAM)",
      origin_coordinates: {
        lat: 35.1017,
        lng: 129.0403,
        matched_code: "KRPUS",
        matched_name: "Port of Busan",
        location_type: "SEAPORT",
        city: "Busan",
        country: "South Korea"
      },
      destination_coordinates: {
        lat: 53.5323,
        lng: 9.9678,
        matched_code: "DEHAM",
        matched_name: "Port of Hamburg",
        location_type: "SEAPORT",
        city: "Hamburg",
        country: "Germany"
      },
      pieces: 1,
      weight: {
        value: 21400.0,
        unit: "KGS"
      },
      volume: 67.2,
      vessel_name: "MAERSK MC-KINNEY MOLLER",
      latest_event: {
        station: "Busan Newport Terminal (KRPUS)",
        status_code: "GATE_IN",
        status_message: "Full export container received at Busan Newport Gate 2",
        event_time: "2026-10-27T06:45:00Z",
        flight_info: "Voyage 261W",
        pieces: 1,
        weight: 21400.0,
        raw_status: "GATE_IN_FULL",
        coordinates: {
          lat: 35.1017,
          lng: 129.0403,
          matched_code: "KRPUS",
          matched_name: "Port of Busan Newport",
          location_type: "SEAPORT",
          city: "Busan",
          country: "South Korea"
        }
      },
      events: [
        {
          station: "Busan Newport Terminal (KRPUS)",
          status_code: "GATE_IN",
          status_message: "Full export container received at Busan Newport Gate 2",
          event_time: "2026-10-27T06:45:00Z",
          flight_info: "Voyage 261W",
          pieces: 1,
          weight: 21400.0,
          coordinates: {
            lat: 35.1017,
            lng: 129.0403,
            matched_code: "KRPUS",
            matched_name: "Port of Busan Newport",
            location_type: "SEAPORT",
            city: "Busan",
            country: "South Korea"
          }
        },
        {
          station: "Busan Customs House (KRPUS)",
          status_code: "CUSTOMS_CLEARED",
          status_message: "Export customs clearance granted by Korea Customs Service",
          event_time: "2026-10-26T14:20:00Z",
          flight_info: null,
          pieces: 1,
          weight: 21400.0,
          coordinates: {
            lat: 35.1017,
            lng: 129.0403,
            matched_code: "KRPUS",
            matched_name: "Busan Customs House",
            location_type: "SEAPORT",
            city: "Busan",
            country: "South Korea"
          }
        },
        {
          station: "Shipper Depot (KRSEL)",
          status_code: "BOOKED",
          status_message: "Shipping booking confirmed with Maersk Logistics",
          event_time: "2026-10-25T18:00:00Z",
          flight_info: null,
          pieces: 1,
          weight: 21400.0,
          coordinates: {
            lat: 37.5665,
            lng: 126.978,
            matched_code: "KRSEL",
            matched_name: "Seoul Regional Office",
            location_type: "SEAPORT",
            city: "Seoul",
            country: "South Korea"
          }
        }
      ],
      agent_trail: {
        detected_mode: "SEA",
        carrier_identified: "Maersk Line (A.P. Moller - Maersk)",
        carrier_code: "MAEU",
        provider_plan: ["maersk_official_direct", "ldb_container"],
        attempts: [
          {
            provider_name: "maersk_official_direct",
            status: "SUCCESS",
            http_status: 200,
            latency_ms: 295.8
          }
        ],
        final_provider_used: "maersk_official_direct"
      }
    },
    mobileApp: {
      awbNumber: "MAEU1234567",
      mode: "SEA",
      carrier: "Maersk Line (A.P. Moller - Maersk)",
      carrierCode: "MAEU",
      trackingStatus: "GATE_IN",
      message: "Container gated in at Busan Newport Terminal",
      origin: "Port of Busan, South Korea (KRPUS)",
      destination: "Port of Hamburg, Germany (DEHAM)",
      originCoordinates: {
        lat: 35.1017,
        lng: 129.0403,
        matched_code: "KRPUS",
        matched_name: "Port of Busan",
        location_type: "SEAPORT",
        city: "Busan",
        country: "South Korea"
      },
      destinationCoordinates: {
        lat: 53.5323,
        lng: 9.9678,
        matched_code: "DEHAM",
        matched_name: "Port of Hamburg",
        location_type: "SEAPORT",
        city: "Hamburg",
        country: "Germany"
      },
      pieces: "1",
      weight: "21400.0",
      weightUnit: "KGS",
      volume: 67.2,
      latestEvent: "Full export container received at Busan Newport Gate 2",
      latestStation: "Busan Newport Terminal (KRPUS)",
      latestTime: "2026-10-27T06:45:00Z",
      events: [
        {
          station: "Busan Newport Terminal (KRPUS)",
          status: "Full export container received at Busan Newport Gate 2",
          statusCode: "GATE_IN",
          time: "2026-10-27T06:45:00Z",
          flight: "Voyage 261W",
          pieces: "1",
          weight: "21400.0",
          lat: 35.1017,
          lng: 129.0403,
          locationName: "Port of Busan Newport"
        },
        {
          station: "Busan Customs House (KRPUS)",
          status: "Export customs clearance granted by Korea Customs Service",
          statusCode: "CUSTOMS_CLEARED",
          time: "2026-10-26T14:20:00Z",
          flight: null,
          pieces: "1",
          weight: "21400.0",
          lat: 35.1017,
          lng: 129.0403,
          locationName: "Busan Customs House"
        },
        {
          station: "Shipper Depot (KRSEL)",
          status: "Shipping booking confirmed with Maersk Logistics",
          statusCode: "BOOKED",
          time: "2026-10-25T18:00:00Z",
          flight: null,
          pieces: "1",
          weight: "21400.0",
          lat: 37.5665,
          lng: 126.978,
          locationName: "Seoul Regional Office"
        }
      ]
    }
  }
};

/**
 * Returns mock tracking data for any container number without performing an API call.
 * If container is in the pre-baked dataset, returns it immediately.
 * Otherwise, synthesizes a realistic dual-payload for that container number.
 */
export function getMockContainerTelemetry(containerNumber) {
  const clean = (containerNumber || "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
  const lookupKey = clean || "MSMU6484830";

  if (MOCK_DATA_STORE[lookupKey]) {
    return MOCK_DATA_STORE[lookupKey];
  }

  // Synthesize realistic data for any custom container number
  const prefix = lookupKey.slice(0, 4);
  let carrierName = "Ocean Network Express (ONE)";
  let carrierCode = "ONEY";

  if (prefix.startsWith("MSM") || prefix.startsWith("MED")) {
    carrierName = "Mediterranean Shipping Company (MSC)";
    carrierCode = "MSCU";
  } else if (prefix.startsWith("MAE")) {
    carrierName = "Maersk Line (A.P. Moller - Maersk)";
    carrierCode = "MAEU";
  } else if (prefix.startsWith("CMA")) {
    carrierName = "CMA CGM Group";
    carrierCode = "CMDU";
  } else if (prefix.startsWith("HLC")) {
    carrierName = "Hapag-Lloyd Container";
    carrierCode = "HLCU";
  }

  const standard = {
    tracking_number: lookupKey,
    container_no: lookupKey,
    mode: "SEA",
    carrier: {
      code: carrierCode,
      prefix: prefix.slice(0, 3),
      name: carrierName,
      mode: "SEA",
      primary_provider: `${carrierCode.toLowerCase()}_direct_api`,
      fallback_providers: ["ldb_container", "searates_broker"]
    },
    status: "IN_TRANSIT",
    message: "Container in maritime transit to destination port",
    origin: "Port of Singapore (SGSIN)",
    destination: "Port of Rotterdam, Netherlands (NLRTM)",
    origin_coordinates: {
      lat: 1.2644,
      lng: 103.8222,
      matched_code: "SGSIN",
      matched_name: "Port of Singapore",
      location_type: "SEAPORT",
      city: "Singapore",
      country: "Singapore"
    },
    destination_coordinates: {
      lat: 51.9554,
      lng: 4.1332,
      matched_code: "NLRTM",
      matched_name: "Port of Rotterdam",
      location_type: "SEAPORT",
      city: "Rotterdam",
      country: "Netherlands"
    },
    pieces: 1,
    weight: { value: 23600.0, unit: "KGS" },
    volume: 67.4,
    vessel_name: "PACIFIC PIONEER",
    latest_event: {
      station: "Malacca Strait Navigational Checkpoint",
      status_code: "IN_TRANSIT",
      status_message: "Vessel underway using engine en route to Suez Canal",
      event_time: "2026-10-27T07:15:00Z",
      flight_info: "Voyage PP26",
      pieces: 1,
      weight: 23600.0,
      coordinates: {
        lat: 2.2,
        lng: 102.25,
        matched_code: "MYMKZ",
        matched_name: "Malacca Strait Checkpoint",
        location_type: "SEAPORT",
        city: "Malacca",
        country: "Malaysia"
      }
    },
    events: [
      {
        station: "Malacca Strait Navigational Checkpoint",
        status_code: "IN_TRANSIT",
        status_message: "Vessel underway using engine en route to Suez Canal",
        event_time: "2026-10-27T07:15:00Z",
        flight_info: "Voyage PP26",
        pieces: 1,
        weight: 23600.0,
        coordinates: {
          lat: 2.2,
          lng: 102.25,
          matched_code: "MYMKZ",
          matched_name: "Malacca Strait Checkpoint",
          location_type: "SEAPORT",
          city: "Malacca",
          country: "Malaysia"
        }
      },
      {
        station: "Port of Singapore (SGSIN)",
        status_code: "LOADED",
        status_message: "Container loaded onboard vessel PACIFIC PIONEER",
        event_time: "2026-10-25T11:40:00Z",
        flight_info: "Voyage PP26",
        pieces: 1,
        weight: 23600.0,
        coordinates: {
          lat: 1.2644,
          lng: 103.8222,
          matched_code: "SGSIN",
          matched_name: "Port of Singapore",
          location_type: "SEAPORT",
          city: "Singapore",
          country: "Singapore"
        }
      },
      {
        station: "Port of Singapore (SGSIN)",
        status_code: "GATE_IN",
        status_message: "Container gated in at PSA Terminal",
        event_time: "2026-10-24T08:30:00Z",
        flight_info: null,
        pieces: 1,
        weight: 23600.0,
        coordinates: {
          lat: 1.2644,
          lng: 103.8222,
          matched_code: "SGSIN",
          matched_name: "Port of Singapore",
          location_type: "SEAPORT",
          city: "Singapore",
          country: "Singapore"
        }
      }
    ],
    agent_trail: {
      detected_mode: "SEA",
      carrier_identified: carrierName,
      carrier_code: carrierCode,
      provider_plan: [`${carrierCode.toLowerCase()}_direct_api`, "ldb_container"],
      attempts: [
        {
          provider_name: `${carrierCode.toLowerCase()}_direct_api`,
          status: "SUCCESS",
          http_status: 200,
          latency_ms: 310.0
        }
      ],
      final_provider_used: `${carrierCode.toLowerCase()}_direct_api`
    }
  };

  const mobileApp = {
    awbNumber: lookupKey,
    mode: "SEA",
    carrier: carrierName,
    carrierCode: carrierCode,
    trackingStatus: "IN_TRANSIT",
    message: "Container in maritime transit to destination port",
    origin: "Port of Singapore (SGSIN)",
    destination: "Port of Rotterdam, Netherlands (NLRTM)",
    originCoordinates: standard.origin_coordinates,
    destinationCoordinates: standard.destination_coordinates,
    pieces: "1",
    weight: "23600.0",
    weightUnit: "KGS",
    volume: 67.4,
    latestEvent: "Vessel underway using engine en route to Suez Canal",
    latestStation: "Malacca Strait Navigational Checkpoint",
    latestTime: "2026-10-27T07:15:00Z",
    events: standard.events.map((ev) => ({
      station: ev.station,
      status: ev.status_message,
      statusCode: ev.status_code,
      time: ev.event_time,
      flight: ev.flight_info,
      pieces: String(ev.pieces || "1"),
      weight: String(ev.weight || "23600.0"),
      lat: ev.coordinates?.lat || null,
      lng: ev.coordinates?.lng || null,
      locationName: ev.coordinates?.matched_name || null
    }))
  };

  return { standard, mobileApp };
}
