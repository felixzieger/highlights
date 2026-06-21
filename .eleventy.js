const yaml = require("js-yaml");
const fs = require("fs");

module.exports = function(eleventyConfig) {

  // Don't try to build pages from these files
  eleventyConfig.addPassthroughCopy("assets");
  eleventyConfig.addPassthroughCopy("README.md");
  eleventyConfig.addPassthroughCopy("robots.txt");

  // Keep highlight data files working after conversion from Jekyll
  eleventyConfig.addDataExtension("yaml", contents => yaml.load(contents));

  // Inline SVG file contents (e.g. icon sprite)
  eleventyConfig.addFilter("svgContents", file =>
    fs.readFileSync(`.${file}`, "utf8")
  );

  return {

    /* Change value if you'd like to deploy to subdirectory, e.g. "/highlights/"
    * Learn more: https://www.11ty.dev/docs/config/#deploy-to-a-subdirectory-with-a-path-prefix
    */
    pathPrefix: "/"

  }

};
