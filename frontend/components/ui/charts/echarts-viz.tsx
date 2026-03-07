'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';

// Purple theme for ECharts
const purpleTheme = {
  color: ['var(--purple-500)', 'var(--purple-500)', 'var(--purple-400)', 'var(--purple-50)', 'var(--silver-400)'],
  backgroundColor: 'transparent',
  textStyle: {
    color: 'var(--silver-500)'
  },
  title: {
    textStyle: {
      color: 'var(--purple-50)'
    }
  },
  line: {
    itemStyle: {
      borderWidth: 1
    },
    lineStyle: {
      width: 2
    },
    symbolSize: 4,
    smooth: true
  },
  categoryAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: 'var(--silver-500)'
      }
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: 'var(--silver-500)'
      }
    },
    axisLabel: {
      show: true,
      color: 'var(--silver-500)'
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: ['var(--black)']
      }
    }
  },  valueAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: 'var(--silver-500)'
      }
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: 'var(--silver-500)'
      }
    },
    axisLabel: {
      show: true,
      color: 'var(--silver-500)'
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: ['var(--black)']
      }
    }
  }
};

// Time Series Chart Component
export const EChartsTimeSeries = () => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetchTimeSeriesData();
  }, []);

  const fetchTimeSeriesData = async () => {
    try {
      const response = await fetch('http://localhost:8000/timeseries?points=50&streams=4');
      const jsonData = await response.json();
      setData(jsonData);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching time series data:', error);
      setLoading(false);
    }
  };
  useEffect(() => {
    if (!chartRef.current || !data) return;

    const myChart = echarts.init(chartRef.current, null, {
      renderer: 'canvas'
    });

    const option = {
      ...purpleTheme,
      title: {
        text: 'Real-Time Metrics Stream',
        textStyle: {
          color: 'var(--purple-50)',
          fontSize: 18
        }
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'var(--black)',
        borderColor: 'var(--purple-500)',
        borderWidth: 1,
        textStyle: {
          color: 'var(--purple-50)'
        }
      },
      legend: {
        data: data.series.map((s: any) => s.name),
        textStyle: {
          color: 'var(--silver-500)'
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: data.timestamps.map((t: string) => new Date(t).toLocaleTimeString()),
        ...purpleTheme.categoryAxis
      },
      yAxis: {
        type: 'value',
        ...purpleTheme.valueAxis
      },
      series: data.series.map((s: any) => ({
        name: s.name,
        type: s.type || 'line',
        smooth: s.smooth,
        areaStyle: s.type === 'area' ? { opacity: 0.3 } : undefined,
        data: s.data,
        lineStyle: {
          width: 2,
          color: s.color
        },
        itemStyle: {
          color: s.color
        }
      }))
    };

    myChart.setOption(option);

    const handleResize = () => {
      myChart.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      myChart.dispose();
    };
  }, [data]);

  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
      {loading ? (
        <div className="h-[400px] flex items-center justify-center">
          <div className="text-purple-400">Loading time series data...</div>
        </div>
      ) : (
        <div ref={chartRef} className="w-full h-[400px]" />
      )}
    </div>
  );
};
// Candlestick Chart Component
export const EChartsCandlestick = () => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetchCandleData();
  }, []);

  const fetchCandleData = async () => {
    try {
      const response = await fetch('http://localhost:8000/candles?days=60');
      const jsonData = await response.json();
      setData(jsonData);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching candle data:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!chartRef.current || !data) return;

    const myChart = echarts.init(chartRef.current, null, {
      renderer: 'canvas'
    });

    const dates = data.candles.map((c: any) => new Date(c.timestamp).toLocaleDateString());
    const ohlcData = data.candles.map((c: any) => [c.open, c.close, c.low, c.high]);
    const volumes = data.candles.map((c: any) => c.volume);

    const option = {
      ...purpleTheme,
      title: {
        text: 'RULE/IQ Trading Data',
        textStyle: {
          color: 'var(--purple-50)',
          fontSize: 18
        }
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'var(--black)',
        borderColor: 'var(--purple-500)',
        borderWidth: 1,
        textStyle: {
          color: 'var(--purple-50)'
        }
      },      legend: {
        data: ['Candlestick', 'MA5', 'MA20', 'Volume'],
        textStyle: {
          color: 'var(--silver-500)'
        }
      },
      grid: [
        {
          left: '10%',
          right: '10%',
          height: '50%'
        },
        {
          left: '10%',
          right: '10%',
          top: '65%',
          height: '16%'
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          axisLine: { lineStyle: { color: 'var(--silver-500)' } },
          axisLabel: { color: 'var(--silver-500)' },
          splitLine: { show: false }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          boundaryGap: false,
          axisLine: { lineStyle: { color: 'var(--silver-500)' } },
          axisLabel: { show: false },
          splitLine: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          axisLine: { lineStyle: { color: 'var(--silver-500)' } },
          axisLabel: { color: 'var(--silver-500)' },
          splitLine: { lineStyle: { color: 'var(--black)' } }
        },
        {
          scale: true,
          gridIndex: 1,
          axisLine: { lineStyle: { color: 'var(--silver-500)' } },
          axisLabel: { color: 'var(--silver-500)' },
          splitLine: { lineStyle: { color: 'var(--black)' } }
        }
      ],      series: [
        {
          name: 'Candlestick',
          type: 'candlestick',
          data: ohlcData,
          itemStyle: {
            color: 'var(--purple-400)',
            color0: 'var(--purple-500)',
            borderColor: 'var(--purple-400)',
            borderColor0: 'var(--purple-500)'
          }
        },
        {
          name: 'MA5',
          type: 'line',
          data: data.indicators.ma5,
          smooth: true,
          lineStyle: {
            width: 1,
            color: 'var(--purple-500)'
          }
        },
        {
          name: 'MA20',
          type: 'line',
          data: data.indicators.ma20,
          smooth: true,
          lineStyle: {
            width: 1,
            color: 'var(--silver-400)'
          }
        },
        {
          name: 'Volume',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          itemStyle: {
            color: 'var(--purple-500)40'
          }
        }
      ]
    };

    myChart.setOption(option);

    const handleResize = () => {
      myChart.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      myChart.dispose();
    };
  }, [data]);

  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
      {loading ? (
        <div className="h-[500px] flex items-center justify-center">
          <div className="text-purple-400">Loading market data...</div>
        </div>
      ) : (
        <div ref={chartRef} className="w-full h-[500px]" />
      )}
    </div>
  );
};