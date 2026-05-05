ARG PYTHON_BASE_IMAGE=python:3.11-slim
FROM ${PYTHON_BASE_IMAGE}

ARG DEFAULT_SIGNAL6_PIPELINE_MODE=v311
ARG ENABLE_FMM_BUILD=1
ARG FMM_BUILD_JOBS=0
ARG APT_MIRROR=
ARG PIP_INDEX_URL=
ARG PIP_TRUSTED_HOST=

ENV DEBIAN_FRONTEND=noninteractive \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	MPLBACKEND=Agg \
	STUDIO_HOME=/opt/studio \
	PYTHONPATH=/opt/studio \
	STUDIO_SIGNAL6_PIPELINE_MODE=${DEFAULT_SIGNAL6_PIPELINE_MODE}

RUN if [ -n "$APT_MIRROR" ]; then \
		sed -i "s|http://deb.debian.org/debian|$APT_MIRROR|g; s|http://security.debian.org/debian-security|$APT_MIRROR-security|g" /etc/apt/sources.list.d/debian.sources; \
	fi && \
	apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update && \
	apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
	build-essential \
	ca-certificates \
	cmake \
	gdal-bin \
	libboost-dev \
	libboost-serialization-dev \
	libfreetype6 \
	libgdal-dev \
	libgomp1 \
	libomp-dev \
	libpng16-16 \
	swig \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /opt/studio

COPY trajectory_annotation_studio/deploy/docker/requirements.runtime.txt /opt/studio/trajectory_annotation_studio/deploy/docker/requirements.runtime.txt

RUN if [ -n "$PIP_INDEX_URL" ]; then \
		python3 -m pip config set global.index-url "$PIP_INDEX_URL"; \
	fi && \
	if [ -n "$PIP_TRUSTED_HOST" ]; then \
		python3 -m pip config set global.trusted-host "$PIP_TRUSTED_HOST"; \
	fi && \
	python3 -m pip install --retries 5 --timeout 60 --upgrade pip && \
	python3 -m pip install --retries 5 --timeout 60 -r /opt/studio/trajectory_annotation_studio/deploy/docker/requirements.runtime.txt

COPY trajectory_annotation_studio /opt/studio/trajectory_annotation_studio
COPY my_history_methods/cellular_quality /opt/studio/my_history_methods/cellular_quality
COPY my_history_methods/map_matching/vendor/fmm /opt/studio/my_history_methods/map_matching/vendor/fmm
COPY project_data/map_assets /opt/studio/project_data/map_assets

WORKDIR /opt/studio/my_history_methods/map_matching/vendor/fmm
RUN if [ "$ENABLE_FMM_BUILD" = "1" ]; then \
		rm -rf build && \
		cmake -S . -B build && \
		if [ "${FMM_BUILD_JOBS}" -gt 0 ] 2>/dev/null; then \
			BUILD_JOBS="${FMM_BUILD_JOBS}"; \
		else \
			BUILD_JOBS="$(nproc)"; \
		fi && \
		cmake --build build --parallel "$BUILD_JOBS"; \
	else \
		echo "Skipping FMM build (ENABLE_FMM_BUILD=$ENABLE_FMM_BUILD)"; \
	fi

WORKDIR /opt/studio
RUN chmod +x /opt/studio/trajectory_annotation_studio/deploy/docker/entrypoint.sh

EXPOSE 8016

ENTRYPOINT ["/opt/studio/trajectory_annotation_studio/deploy/docker/entrypoint.sh"]
