import { Link } from "react-router-dom";
import { Upload } from "lucide-react";
import { PhotoBrowser } from "../components/PhotoBrowser";
import { Button, PageHeading } from "../components/ui";

export function PhotosPage() {
  return <PhotoBrowser rememberAs="photos" header={(total) => (
    <PageHeading title="Photos" description={total === null ? undefined : `${total.toLocaleString()} ${total === 1 ? "photo" : "photos"}`}
      action={<Link to="/upload"><Button><Upload className="h-4 w-4" />Upload</Button></Link>} />
  )} />;
}
