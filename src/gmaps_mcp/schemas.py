"""Pydantic schemas and data models for Google Maps MCP Server."""

from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class Place(BaseModel):
    """Structured representation of a Google Maps place or business."""

    model_config = ConfigDict(extra="ignore")

    place_id: str = Field(
        description="Unique Google Maps Place ID (e.g., 'ChIJ...' or CID identifier)"
    )
    name: str = Field(
        description="Official name of the place, business, or landmark"
    )
    category: Optional[str] = Field(
        default=None,
        description="Primary business or location category (e.g., 'Coffee shop', 'Hospital', 'Restaurant')"
    )
    address: Optional[str] = Field(
        default=None,
        description="Full street address of the location"
    )
    phone: Optional[str] = Field(
        default=None,
        description="Local telephone number (e.g., '(206) 780-5777' or '080 2553 1234')"
    )
    international_phone: Optional[str] = Field(
        default=None,
        description="International E.164 formatted phone number (e.g., '+91 80 2553 1234')"
    )
    website: Optional[str] = Field(
        default=None,
        description="Full destination URL of the business website"
    )
    domain: Optional[str] = Field(
        default=None,
        description="Domain name of the website (e.g., 'example.com')"
    )
    latitude: Optional[float] = Field(
        default=None,
        description="Geographic latitude coordinate (WGS84)"
    )
    longitude: Optional[float] = Field(
        default=None,
        description="Geographic longitude coordinate (WGS84)"
    )
    rating: Optional[float] = Field(
        default=None,
        description="Average Google customer star rating (0.0 to 5.0)"
    )
    review_count: Optional[int] = Field(
        default=None,
        description="Total number of customer reviews"
    )
    google_maps_url: Optional[str] = Field(
        default=None,
        description="Direct URL to view this place on Google Maps"
    )


class SearchGoogleMapsResult(BaseModel):
    """Result object returned by the search_google_maps tool."""

    query: str = Field(description="The search query that was executed")
    country: str = Field(description="The ISO 3166-1 alpha-2 country code used (e.g., 'in', 'us')")
    language: str = Field(description="The language code used for results (e.g., 'en', 'hi')")
    total_results: int = Field(description="Number of places returned in this response")
    places: List[Place] = Field(default_factory=list, description="List of matched Google Maps places")


class GetPlaceDetailsResult(BaseModel):
    """Result object returned by the get_place_details tool."""

    place: Optional[Place] = Field(
        default=None,
        description="The retrieved place object if found, otherwise null"
    )
    found: bool = Field(
        default=False,
        description="Whether the place was successfully found"
    )
    query_or_id: str = Field(
        description="The place query or Place ID searched for"
    )
